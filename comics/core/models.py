import os

from django.conf import settings
from django.db import models
from django.core.files.storage import FileSystemStorage
from django.core.urlresolvers import reverse

from comics.core.managers import ComicManager

class Comic(models.Model):
    LANGUAGES = (
        ('en', 'English'),
        ('no', 'Norwegian'),
    )

    # Required fields
    name = models.CharField(max_length=100,
        help_text='Name of the comic')
    slug = models.SlugField(max_length=100, unique=True,
        verbose_name='Short name',
        help_text='For file paths and URLs')
    language = models.CharField(max_length=2, choices=LANGUAGES,
        help_text='The language of the comic')
    url = models.URLField(verbose_name='URL', blank=True,
        help_text='URL to the official website')

    # Optional fields
    start_date = models.DateField(blank=True, null=True,
        help_text='First published at')
    end_date = models.DateField(blank=True, null=True,
        help_text='Last published at, if comic has been cancelled')
    rights = models.CharField(max_length=100, blank=True,
        help_text='Author, copyright, and/or licensing information')

    # Automatically populated fields (i.e. for denormalization)
    number_of_sets = models.PositiveIntegerField(default=0,
        help_text='Number of sets the comic is in (automatically updated)')

    objects = ComicManager()

    class Meta:
        db_table = 'comics_comic'
        ordering = ['name']

    def __unicode__(self):
        return u'%s [%s]' % (self.name, self.language)

    def get_absolute_url(self):
        return reverse('comic-latest', kwargs={
            'comic': self.slug,
        })

    def get_feed_url(self):
        return reverse('feeds', kwargs={
            'url': 'c/%s' % self.slug,
        })


class Release(models.Model):
    # XXX An index ranging over all three fields of this class is CRITICAL for
    # any performance. For PostreSQL use:
    #
    #     CREATE INDEX "comics_release_comic_id_pub_date_strip_id"
    #         ON "comics_release" ("comic_id", "pub_date", "strip_id");

    # Required fields
    comic = models.ForeignKey(Comic)
    pub_date = models.DateField(verbose_name='publication date')
    strip = models.ForeignKey('Strip', related_name='releases')

    class Meta:
        db_table = 'comics_release'
        get_latest_by = 'pub_date'

    def __unicode__(self):
        return u'%s published %s' % (self.comic, self.pub_date)

    def get_absolute_url(self):
        return reverse('comic-date', kwargs={
            'comic': self.comic.slug,
            'year': self.pub_date.year,
            'month': self.pub_date.month,
            'day': self.pub_date.day,
        })


# Let all created dirs and files be writable by the group
os.umask(0002)

strip_storage = FileSystemStorage(
    location=settings.COMICS_MEDIA_ROOT, base_url=settings.COMICS_MEDIA_URL)

def strip_file_path(instance, filename):
    return u'%s/%s/%s' % (instance.comic.slug, filename[0], filename)

class Strip(models.Model):
    # Required fields
    comic = models.ForeignKey(Comic)
    fetched = models.DateTimeField(auto_now_add=True)
    file = models.ImageField(storage=strip_storage, upload_to=strip_file_path,
        height_field='height', width_field='width')
    height = models.IntegerField()
    width = models.IntegerField()
    checksum = models.CharField(max_length=64, db_index=True)

    # Optional fields
    title = models.CharField(max_length=255, blank=True)
    text = models.TextField(blank=True)

    class Meta:
        db_table = 'comics_strip'
        get_latest_by = 'pub_date'

    def delete(self, *args, **kwargs):
        super(Strip, self).delete(*args, **kwargs)
        os.remove(self.file.path)

    def __unicode__(self):
        return u'%s strip %s' % (self.comic, self.checksum)

    def get_first_release(self):
        return self.releases.order_by('pub_date')[0]