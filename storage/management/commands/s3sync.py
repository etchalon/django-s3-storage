import os
import mimetypes
import datetime, time, calendar
import gzip
from datetime import date, timedelta

from optparse import make_option
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.core.files.base import ContentFile
from django.conf import settings
from storage import path, S3

try:
	from cStringIO import StringIO
except ImportError:
	from StringIO import StringIO

GZIP_FILE_TYPES = ('text/css','text/javascript','application/javascript','application/x-javascript',)

class Command(BaseCommand):
	option_list = BaseCommand.option_list + (make_option('--only', '-o', default='', dest='only_subdirectory', help='Only sync a specific subdirectory of MEDIA_ROOT'), 
					make_option('--force', '-f', action="store_true", dest='force', help='Upload all files, regardless of modification dates'),)
	help = ('Uploads files from the MEDIA_ROOT to the DEFAULT_BUCKET, replacing newer files.')
	requires_model_validation = False
	can_import_settings = True
	
	def handle(self, *args, **kwargs):
		return init(*args, **kwargs)


def init(*args, **kwargs):
	directory = kwargs.get('only_subdirectory','')
	force = kwargs.get('force', False)
	traverse(settings.MEDIA_ROOT + directory, upload_to_s3, force=force)


def traverse(directory, function, depth=0, force=False):
	thedir = path.path(directory)
	for item in thedir.files():
		function(item, depth, force)
	for item in thedir.dirs():
		if os.path.basename(item.realpath())[0] != '.':			
			traverse(item, function, depth+1, force)


def upload_to_s3(item, depth=0, force=False):
	upload_this = False
	download_this = False
	item_name = item.realpath().split(settings.MEDIA_ROOT)[1]
	item_path = os.path.basename(item.realpath())	
	if item_path[0] == '.':
		return
	if default_storage.exists(item_name):
		local_time = os.path.getmtime(item.realpath())
		server_time = default_storage.getmtime(item_name)
		if server_time < local_time:
			print '%s is newer locally' % item_name
			upload_this = True
	else:
		upload_this = True
	if force:
		upload_this = True
	if upload_this:
		filedata = open(item.realpath(), 'rb').read()
		content_type = mimetypes.guess_type(item.realpath())[0]
		print "Uploading %s as %s" % (item_name, content_type)		
		if not content_type:
			content_type = 'text/plain'
		io = StringIO()
		io.write(open(item.realpath(), 'rb').read())
		tenyrs = date.today() + timedelta(days=365*10)
		if content_type in GZIP_FILE_TYPES:
			print '... gzipping file'
			zbuffer = StringIO()
			zfile = gzip.GzipFile(mode='wb', compresslevel=6, fileobj=zbuffer)
			zfile.write(io.getvalue())
			zfile.close()
			file_object = ContentFile(zbuffer.getvalue())
			default_storage._save(item_name, file_object, {'Content-Encoding':'gzip',})
		else:
			file_object = ContentFile(io.getvalue())
			default_storage._save(item_name, file_object)