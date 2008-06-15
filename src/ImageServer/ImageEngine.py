import Image, ImageOps
import mimetypes
import os, os.path, shutil
from ImageServer import Domain, Persistence

# Relative to the data_directory
CACHE_DIRECTORY = "cache"
ORIGINAL_DIRECTORY = "pictures"
FORMAT_EXTENSIONS = { "JPEG" : "jpg" }

# Layout
# data/original/image_id.format
# data/cache/image_id/800x600/format

def checkid(imageId):
    if not imageId.isalnum():
        raise ImageProcessingException, 'ID contains non alpha numeric characters: %s' % imageId
            
class ImageProcessingException(Exception):
    """Thrown when errors happen while processing images """
    def __init__(self, message):
        Exception.__init__(self, message)

class TransformationRequest(object):
    """ Stores the parameters of an image processing request """
    def __init__(self, image_id, size, target_format):
        """ @param size: a (width, height) tuple
        """
        checkid(image_id)
        
        self.image_id = image_id
        self.size = size
        self.target_format = target_format

class ImageRequestProcessor(object):
    
    """ Processes ImageRequest objects and does the required work to prepare the images """
    def __init__(self, itemRepository, dataDirectory):
        """ @param data_directory: the directory that this 
            ImageRequestProcessor will use for its work files """
        self.__dataDirectory = dataDirectory 
        self.__initDirectories()
        self.__itemRepository = itemRepository
        
    def __initDirectories(self):
        """ Creates the work directories needed to run this processor """
        for directory in \
            [self.__absoluteCacheDirectory(), self.__absoluteOriginalDirectory()]:
            if not os.path.exists(directory):
                os.makedirs(directory)
        
    def __absoluteCacheDirectory(self):
        """ @return: the directory that will be used for caching image processing 
        results """
        return os.path.join(self.__dataDirectory, CACHE_DIRECTORY)
    
    def __absoluteOriginalDirectory(self):
        """ @return. the directory that will be used to store original files, 
        before processing"""
        return os.path.join (self.__dataDirectory, ORIGINAL_DIRECTORY)
    
    def __absoluteOriginalFilename(self, originalItem):
        """ returns the filename of the original file """
        return os.path.join (self.__absoluteOriginalDirectory(), '%s.%s' % (originalItem.id, self.__extensionForFormat(originalItem.format)))
    
    def __absoluteCachedFilename(self, derivedItem):
        
        return os.path.join( self.__dataDirectory,
                            self.__relativeCachedFilename(derivedItem))
    
    def __relativeCachedFilename(self, derivedItem):
        """ relative to the base directory """
        return os.path.join ( CACHE_DIRECTORY, 
                              '%s-%sx%s.%s' % (derivedItem.id, derivedItem.size[0], derivedItem.size[1],self.__extensionForFormat(derivedItem.format)))
        
    def __extensionForFormat(self, format):
        return FORMAT_EXTENSIONS[format.upper()] if FORMAT_EXTENSIONS.__contains__(format.upper()) else format.lower()

    def saveFileToRepository(self, filename, image_id):
        """ save the given file to the image server repository. 
        It will then be available for transformations"""
        
        checkid(image_id)
        img = Image.open(filename)
        
        # Check that the image is not broken
        img = Image.open(filename)
        img.verify()
        
        item = Domain.OriginalItem(image_id, Domain.STATUS_INCONSISTENT, img.size, img.format)
        
        try:
            self.__itemRepository.create(item)
        except Persistence.DuplicateEntryException, ex:
            raise ImageProcessingException, 'an image with the given ID already exists in the repository'
        else:
            try:
                shutil.copyfile(filename, self.__absoluteOriginalFilename(item))
            except IOError, ex:
                raise ImageProcessingException, ex
        
        item.status = Domain.STATUS_OK
        self.__itemRepository.update(item)
    
    def prepareTransformation(self, transformation_request):
        """ Takes an ImageRequest and prepare the output for it.
            @return: the path to the generated file (relative to the cache directory) 
            """
        originalItem = self.__itemRepository.findOriginalItemById(transformation_request.image_id)
        assert originalItem is not None
        assert originalItem.status == Domain.STATUS_OK
        
        derivedItem = Domain.DerivedItem(Domain.STATUS_INCONSISTENT, transformation_request.size, transformation_request.target_format, originalItem)
        
        cached_filename = self.__absoluteCachedFilename(derivedItem)
        relative_cached_filename = self.__relativeCachedFilename(derivedItem)

        # if image is already cached...
        if os.path.exists(cached_filename):
            return relative_cached_filename
        
        # otherwise, c'est parti to convert the stuff
        original_filename = self.__absoluteOriginalFilename(originalItem)
        try:
            img = Image.open(original_filename)
        except IOError, ex: 
            raise ImageProcessingException, ex
        
        if transformation_request.size == img.size and transformation_request.target_format.upper() == img.format.upper():
            try:
                shutil.copyfile(self.__absoluteOriginalFilename(originalItem), cached_filename)
            except IOError, ex:
                raise ImageProcessingException, ex
        else:   
            target_image = ImageOps.fit(image=img, 
                                        size=transformation_request.size, 
                                        method=Image.ANTIALIAS,
                                        centering=(0.5,0.5)) 
            try:
                target_image.save(cached_filename)
            except IOError, ex:
                raise ImageProcessingException, ex
        
        derivedItem.status = Domain.STATUS_OK
        self.__itemRepository.update(derivedItem)
        
        return cached_filename
    
    

