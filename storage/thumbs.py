# Based on django-thumbs by Antonio Mel

import logging

try:
	from cStringIO import StringIO
except ImportError:
	from StringIO import StringIO

from django.db.models import ImageField
from django.db.models.fields.files import ImageFieldFile
from django.utils.functional import curry
from django.core.files.base import ContentFile

from PIL import Image, ImageOps


DEFAULT_RESAMPLING_METHOD = Image.ANTIALIAS


def generate_thumbnail(image_file_object, thumbnail_spec, output_format, quality=95):
	image_file_object.seek(0) # see http://code.djangoproject.com/ticket/8222 for details
	image = Image.open(image_file_object)
	image_modified = False
	if len(thumbnail_spec) == 4:
		thumbnail_width, thumbnail_height, force_width, force_height = thumbnail_spec
		force_aspect = False
	elif len(thumbnail_spec) == 5:
		thumbnail_width, thumbnail_height, force_width, force_height, force_aspect = thumbnail_spec
	thumbnail_size = (thumbnail_width, thumbnail_height)
	transparency = image.info.get('transparency')
	if image.size != thumbnail_size:
		if force_aspect:
			image_width, image_height = image.size
			if image_width > image_height:
				image_modified = True
				image = ImageOps.fit(image, thumbnail_size, DEFAULT_RESAMPLING_METHOD)
			elif image_width < image_height:
				image_modified = True
				thumbnail_size = (thumbnail_height, thumbnail_width,)
				image = ImageOps.fit(image, thumbnail_size, DEFAULT_RESAMPLING_METHOD)
			else:
				image_modified = True
				thumbnail_size = (thumbnail_height, thumbnail_height,)
				image = ImageOps.fit(image, thumbnail_size, DEFAULT_RESAMPLING_METHOD)				
		elif force_width or force_height:
			image_modified = True
			image_width, image_height = image.size
			if force_width:
				if force_height: # Crop the image to desired size
					image = ImageOps.fit(image, thumbnail_size, DEFAULT_RESAMPLING_METHOD)
				else:
					wpercent = thumbnail_width / float(image_width)
					hsize = int(image_height * wpercent)
					image = image.resize((thumbnail_width, hsize), DEFAULT_RESAMPLING_METHOD)
			else:
				if force_height:		
					hpercent = thumbnail_height / float(image_height)
					wsize = int(image_width * hpercent)
					image = image.resize((wsize, thumbnail_height), DEFAULT_RESAMPLING_METHOD)
				else: # Resize the image while maintaining original aspect ratio
					image.thumbnail(thumbnail_size, DEFAULT_RESAMPLING_METHOD)
		else:
			image_width, image_height = image.size
			if thumbnail_width > 0 and image_width > thumbnail_width:
				image_modified = True
				wpercent = thumbnail_width / float(image_width)
				hsize = int(image_height * wpercent)
				image = image.resize((thumbnail_width, hsize), DEFAULT_RESAMPLING_METHOD)

	if output_format.upper() == 'JPG':
		output_format = 'JPEG'
	if transparency is not None:
		options = {'transparency': transparency}
	else:
		options = {'quality': quality}
	if image_modified:
		io = StringIO()
		image.save(io, output_format, **options)
		return ContentFile(io.getvalue())
	else:
		image_file_object.seek(0)
		return image_file_object

def get_full_url(name, storage, thumbnail_spec, image_file_object=None):

	file_name, file_extension = name.rsplit('.', 1)
	thumbnail_width, thumbnail_height = thumbnail_spec[:2]
	if len(thumbnail_spec) == 4:
		thumbnail_url = "%s.%sx%s.%s" % (file_name, thumbnail_width, thumbnail_height, file_extension)
	elif len(thumbnail_spec) == 5:
		thumbnail_url = "%s.%sx%s.aspect.%s" % (file_name, thumbnail_width, thumbnail_height, file_extension)		

	if storage.exists(thumbnail_url):
		return storage.url(thumbnail_url)
	try:
		if image_file_object is None:
			if storage.exists(name):
				io = StringIO()
				io.write(storage.open(name).read())
				image_file_object = ContentFile(io.getvalue()) 
			else:
				return None
		thumb_name = storage.save(thumbnail_url, generate_thumbnail(image_file_object, thumbnail_spec, file_extension))
	except:
		return None
	return storage.url(thumbnail_url)


class ImageWithThumbsFieldFile(ImageFieldFile):
	def __init__(self, *args, **kwargs):		
		super(ImageWithThumbsFieldFile, self).__init__(*args, **kwargs)
		if self.field.sizes:
			for thumbnail_spec in self.field.sizes:
				thumbnail_size = thumbnail_spec[:2]
				setattr(self, 'url_%sx%s' % thumbnail_size,curry(self._get_full_url, thumbnail_spec=thumbnail_spec))
				
	def _get_full_url(self, thumbnail_spec, image_file_object=None):
		if not self: # Sanity check
			return ''
		return get_full_url(self.name, self.storage, thumbnail_spec, image_file_object)

	def generate_all_thumbnails(self, content=None):
		if self.field.sizes:
			for thumbnail_spec in self.field.sizes:
				self._get_full_url(thumbnail_spec, content)
				
	def save(self, name, content, save=True):
		super(ImageWithThumbsFieldFile, self).save(name, content, save)
		self.generate_all_thumbnails(content)
						
	def delete(self, save=True):
		name=self.name
		super(ImageWithThumbsFieldFile, self).delete(save)
		if self.field.sizes:
			for thumbnail_spec in self.field.sizes:
				file_name, file_extension = name.rsplit('.', 1)
				thumbnail_width, thumbnail_height = thumbnail_spec[:2]
				thumbnail_url = "%s.%sx%s.%s" % (
					file_name,
					thumbnail_width,
					thumbnail_height,
					file_extension
				)	
				try:
					self.storage.delete(thumbnail_url)
				except:
					pass

				
class ImageWithThumbsField(ImageField):
	attr_class = ImageWithThumbsFieldFile
	"""
	Usage example:
	==============
	photo = ImageWithThumbsField(upload_to='images', sizes=((125,125, False, False),(300,200, True, True),)
	
	To retrieve image URL, exactly the same way as with ImageField:
		my_object.photo.url
	To retrieve thumbnails URL's just add the size to it:
		my_object.photo.url_125x125
		my_object.photo.url_300x200
	
	Note: The 'sizes' attribute is not required. If you don't provide it, 
	ImageWithThumbsField will act as a normal ImageField
		
	How it works:
	=============
	For each size in the 'sizes' atribute of the field it generates a 
	thumbnail with that size and stores it following this format:
	
	available_filename.[width]x[height].extension

	Where 'available_filename' is the available filename returned by the storage
	backend for saving the original file.
	
	Following the usage example above: For storing a file called "photo.jpg" it saves:
	photo.jpg		  (original file)
	photo.125x125.jpg  (first thumbnail)
	photo.300x200.jpg  (second thumbnail)
	
	With the default storage backend if photo.jpg already exists it will use these filenames:
	photo_.jpg
	photo_.125x125.jpg
	photo_.300x200.jpg
	
	Note: django-thumbs assumes that if filename "any_filename.jpg" is available 
	filenames with this format "any_filename.[widht]x[height].jpg" will be available, too.
	"""
	def __init__(self, verbose_name=None, name=None, width_field=None, height_field=None, sizes=None, **kwargs):
		self.verbose_name=verbose_name
		self.name=name
		self.width_field=width_field
		self.height_field=height_field
		self.sizes = sizes
		super(ImageField, self).__init__(**kwargs)
