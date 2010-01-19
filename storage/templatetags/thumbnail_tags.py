import os, sys, traceback, urllib
from django import template
from django.conf import settings
from django.utils.encoding import force_unicode, iri_to_uri
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.cache import cache

from storage.thumbs import generate_thumbnail, get_full_url
from hss.utils import create_cache_key

try:
	from cStringIO import StringIO
except ImportError:
	from StringIO import StringIO

register = template.Library()


class ThumbnailNode(template.Node):
	def __init__(self, source, width, height, quality=None, dest=None,
				 as_var=None):
		self.image_source = template.Variable(source)
		self.width = template.Variable(width)
		self.height = template.Variable(height)
		if quality is not None and quality != 'None':
			self.quality = template.Variable(quality)
		else:
			self.quality = None
		if dest is not None:
			self.dest = template.Variable(dest)
		else:
			self.dest = None
		self.as_var = as_var
		self.storage = default_storage

	def render(self, context):
		if self.image_source is not None:
			source = self.image_source.resolve(context)
		if self.width is not None:
			width = self.width.resolve(context)
		if self.height is not None:
			height = self.height.resolve(context)
		if self.quality is not None:
			quality = self.quality.resolve(context)
		else:
			quality = 95
		if self.dest is not None:			
			dest = self.dest.resolve(context)
		else:
			dest = None	
		
		cache_key = create_cache_key('thumnbail', source, width, height, quality, dest)
		thumburl = cache.get(cache_key)
		try:
			if thumburl is None:
				thumburl = source._get_full_url((width, height, True, True))
				cache.set(cache_key, thumburl)
		except:
			thumburl = None
			
		if self.as_var:
			context[self.as_var] = thumburl
			return ''
		else:
			return thumburl
	
	def thumbnail_url(self, source, height, width):
		file_name, file_extension = source.rsplit('.', 1)
		thumbnail_width, thumbnail_height = width, height
		thumbnail_url = "%s.%sx%s.%s" % (file_name, thumbnail_width, thumbnail_height, file_extension)
		return thumbnail_url
		
	def create_thumbail():
		return ''

class MaxSizeNode(ThumbnailNode):
	
	def render(self, context):
		if self.image_source is not None:
			source = self.image_source.resolve(context)
		if self.width is not None:
			width = self.width.resolve(context)
		if self.height is not None:
			height = self.height.resolve(context)
		if self.quality is not None:
			quality = self.quality.resolve(context)
		else:
			quality = 95
		if self.dest is not None:			
			dest = self.dest.resolve(context)
		else:
			dest = None	
		
		cache_key = create_cache_key('maxsize', source, width, height, quality, dest)
		thumburl = cache.get(cache_key)
		
		if thumburl is None:
			thumburl = source._get_full_url((width, height, False, False))
			cache.set(cache_key, thumburl)
			
		if self.as_var:
			context[self.as_var] = thumburl
			return ''
		else:
			return thumburl	
			
class AspectSizeNode(ThumbnailNode):

	def render(self, context):
		if self.image_source is not None:
			source = self.image_source.resolve(context)
		if self.width is not None:
			width = self.width.resolve(context)
		if self.height is not None:
			height = self.height.resolve(context)
		if self.quality is not None:
			quality = self.quality.resolve(context)
		else:
			quality = 95
		if self.dest is not None:			
			dest = self.dest.resolve(context)
		else:
			dest = None	

		cache_key = create_cache_key('aspect', source, width, height, quality, dest)
		thumburl = cache.get(cache_key)
		
		if thumburl is None:
			thumburl = source._get_full_url((width, height, False, False, True))
			cache.set(cache_key, thumburl)

		if self.as_var:
			context[self.as_var] = thumburl
			return ''
		else:
			return thumburl			

def do_thumbnail(parser, token):
	"""
	Creates a thumbnail if needed and displays its url.
	Usage::
		{% thumbnail source width height [quality] [destination] %}
	Source and destination can be a file like object or a path as a string.
	"""
	split_token = token.split_contents()
	vars = []
	as_var = False
	for k, v in enumerate(split_token[1:]):
		if v == 'as':
			try:
				while len(vars) < 5:
					vars.append(None)
				vars.append(split_token[k+2])
				as_var = True
			except IndexError:
				raise template.TemplateSyntaxError, "%r tag requires a variable name to attach to" % split_token[0]
			break
		else:
			vars.append(v)
	if (not as_var and len(vars) not in (3, 4, 5)) or (as_var and len(vars) not in (4, 5, 6)):
		raise template.TemplateSyntaxError, "%r tag requires a source, a width and a height" % token.contents.split()[0]
	return ThumbnailNode(*vars)
	

def do_maxsize(parser, token):
	"""
	Creates a thumbnail if needed and displays its url.
	Usage::
		{% thumbnail source width height [quality] [destination] %}
	Source and destination can be a file like object or a path as a string.
	"""
	split_token = token.split_contents()
	vars = []
	as_var = False
	for k, v in enumerate(split_token[1:]):
		if v == 'as':
			try:
				while len(vars) < 5:
					vars.append(None)
				vars.append(split_token[k+2])
				as_var = True
			except IndexError:
				raise template.TemplateSyntaxError, "%r tag requires a variable name to attach to" % split_token[0]
			break
		else:
			vars.append(v)
	if (not as_var and len(vars) not in (3, 4, 5)) or (as_var and len(vars) not in (4, 5, 6)):
		raise template.TemplateSyntaxError, "%r tag requires a source, a width and a height" % token.contents.split()[0]
	return MaxSizeNode(*vars)	

def do_aspectsize(parser, token):
	"""
	Creates a thumbnail if needed and displays its url.
	Usage::
		{% thumbnail source width height [quality] [destination] %}
	Source and destination can be a file like object or a path as a string.
	"""
	split_token = token.split_contents()
	vars = []
	as_var = False
	for k, v in enumerate(split_token[1:]):
		if v == 'as':
			try:
				while len(vars) < 5:
					vars.append(None)
				vars.append(split_token[k+2])
				as_var = True
			except IndexError:
				raise template.TemplateSyntaxError, "%r tag requires a variable name to attach to" % split_token[0]
			break
		else:
			vars.append(v)
	if (not as_var and len(vars) not in (3, 4, 5)) or (as_var and len(vars) not in (4, 5, 6)):
		raise template.TemplateSyntaxError, "%r tag requires a source, a width and a height" % token.contents.split()[0]
	return AspectSizeNode(*vars)	


do_thumbnail = register.tag('thumbnail', do_thumbnail)
do_maxsize = register.tag('maxsize', do_maxsize)
do_aspectsize = register.tag('aspect', do_aspectsize)