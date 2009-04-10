"""
    ImgServer RESTful Image Conversion Service 
    Copyright (C) 2008 Sami Dalouche

    This file is part of ImgServer.

    ImgServer is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    ImgServer is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with ImgServer.  If not, see <http://www.gnu.org/licenses/>.

"""
from __future__ import with_statement
import os
import os.path
import shutil
import time
import Image, ImageOps
from zope.interface import Interface, implements
from imgserver import domain
from imgserver import persistence
from imgserver import imgengine
from imgserver.domain.abstractitem import AbstractItem
from imgserver.domain.originalitem import OriginalItem
from imgserver.domain.deriveditem import DerivedItem
from imgserver.domain.itemrepository import DuplicateEntryException

CACHE_DIRECTORY = "cache"
ORIGINAL_DIRECTORY = "pictures"
FORMAT_EXTENSIONS = { "JPEG" : "jpg" }

LOCK_MAX_RETRIES = 10
LOCK_WAIT_SECONDS = 1
        
class IImageRequestProcessor(Interface):
    """ Processes ImageRequest objects and does the required work to prepare the images """
    
    def getOriginalImagePath(self, item_id):
        """@return: the relative path of the original image that has the given item_id 
        @rtype: str
        @raise ItemDoesNotExistError: if item_id does not exist"""
        
    def saveFileToRepository(self, file, imageId):
        """ save the given file to the image server repository. 
        It will then be available for transformations
        @param file: either a filename or a file-like object 
        that is opened in binary mode
        """
    
    def prepareTransformation(self, transformationRequest):
        """ Takes an ImageRequest and prepare the output for it. 
        Updates the database so that it is in sync with the filesystem
        @return: the path to the generated file (relative to the data directory)
        @raise ItemDoesNotExistError: if item_id does not exist
        @raise ImageProcessingException in case of any non-recoverable error 
        """
    
    def _cleanupInconsistentItems(self):
        """ deletes the files and items whose status is not OK (startup cleanup)"""

class ItemDoesNotExistError(Exception):
    def __init__(self,item_id):
        super(ItemDoesNotExistError, self).__init__()
        self.item_id = item_id

class ImageRequestProcessor(object):
    implements(IImageRequestProcessor)
    
    def __init__(self, itemRepository, persistenceProvider, dataDirectory, drop_data=False):
        """ @param data_directory: the directory that this 
            ImageRequestProcessor will use for its work files """
        self.__dataDirectory = dataDirectory 
        self.__itemRepository = itemRepository
        self.__persistenceProvider = persistenceProvider
        
        if drop_data:
            self.__drop_data()
        
        self.__init_data()
        self._cleanupInconsistentItems()
        
    def __initDirectories(self):
        """ Creates the work directories needed to run this processor """
        
        
    def __absoluteCacheDirectory(self):
        """ @return: the directory that will be used for caching image processing 
        results """
        return os.path.join(self.__dataDirectory, CACHE_DIRECTORY)
    
    def __absoluteOriginalDirectory(self):
        """ @return. the directory that will be used to store original files, 
        before processing"""
        return os.path.join (self.__dataDirectory, ORIGINAL_DIRECTORY)
    
    def __absoluteOriginalFilename(self, original_item):
        """ returns the filename of the original file """
        return os.path.join (self.__absoluteOriginalDirectory(), '%s.%s' % (original_item.id, self.__extensionForFormat(original_item.format)))
    
    def __absoluteCachedFilename(self, derivedItem):
        
        return os.path.join( self.__dataDirectory,
                            self.__relativeCachedFilename(derivedItem))
    
    def __relativeCachedFilename(self, derivedItem):
        """ relative to the base directory """
        return os.path.join ( CACHE_DIRECTORY, 
                              '%s-%sx%s.%s' % (derivedItem.original_item.id, derivedItem.size[0], derivedItem.size[1],self.__extensionForFormat(derivedItem.format)))
        
    def __extensionForFormat(self, format):
        return FORMAT_EXTENSIONS[format.upper()] if FORMAT_EXTENSIONS.__contains__(format.upper()) else format.lower()

    def __waitForItemStatusOk(self, pollingCallback):
        """ Wait for the status property of the object returned by pollingCallback() to be STATUS_OK
        It honors LOCK_MAX_RETRIES and LOCK_WAIT_SECONDS
        """
        item = pollingCallback()
        i = 0
        while i < LOCK_MAX_RETRIES and item is not None and item.status != domain.STATUS_OK:
            time.sleep(LOCK_WAIT_SECONDS)
            item = pollingCallback()
            i=i+1
    
    def __wait_for_original_item(self, item_id):
        """ Wait for the given original item to have a status of STATUS_OK """
        self.__waitForItemStatusOk(lambda: self.__itemRepository.findOriginalItemById(item_id))
    
    def __required_original_item(self, item_id, original_item):
        if original_item is None:
            raise ItemDoesNotExistError(item_id)
    
    def originalImageExists(self, item_id):
        original_item = self.__itemRepository.findOriginalItemById(item_id)
        return original_item is not None
                
    def getOriginalImagePath(self, item_id):
        original_item = self.__itemRepository.findOriginalItemById(item_id)
        self.__required_original_item(item_id, original_item)
        self.__wait_for_original_item(item_id)
        return os.path.join (ORIGINAL_DIRECTORY, '%s.%s' % (original_item.id, self.__extensionForFormat(original_item.format)))
                               
    def saveFileToRepository(self, file, imageId):
        def filenameSaveStrategy(file, item):
            shutil.copyfile(file, self.__absoluteOriginalFilename(item))
        
        def fileLikeSaveStrategy(file, item):
            file.seek(0)
            with open(self.__absoluteOriginalFilename(item), "w+b") as out:
                shutil.copyfileobj(file, out)
                out.flush()

        imgengine.checkid(imageId)
        
        if type(file) == str:
            save = filenameSaveStrategy
        else:
            save = fileLikeSaveStrategy
        
        # Check that the image is not broken
        try:
            img = Image.open(file)
            img.verify()
        except IOError, ex:
            raise imgengine.ImageFileNotRecognized(ex)
        
        item = OriginalItem(imageId, domain.STATUS_INCONSISTENT, img.size, img.format)

        try:
            # atomic creation
            self.__itemRepository.create(item)
        except DuplicateEntryException, ex:
            raise imgengine.ImageIDAlreadyExistingException(item.id)
        else:
            try:
                save(file, item)
            except IOError, ex:
                raise imgengine.ImageProcessingException(ex)
        
        item.status = domain.STATUS_OK
        self.__itemRepository.update(item)
            
    def prepareTransformation(self, transformationRequest):
        original_item = self.__itemRepository.findOriginalItemById(transformationRequest.imageId)
        self.__required_original_item(transformationRequest.imageId, original_item)
        
        self.__wait_for_original_item(transformationRequest.imageId)
        derivedItem = DerivedItem(domain.STATUS_INCONSISTENT, transformationRequest.size, transformationRequest.targetFormat, original_item)
        
        cached_filename = self.__absoluteCachedFilename(derivedItem)
        relative_cached_filename = self.__relativeCachedFilename(derivedItem)

        # if image is already cached...
        if os.path.exists(cached_filename):
            return relative_cached_filename
        
        # otherwise, c'est parti to convert the stuff
        try:
            self.__itemRepository.create(derivedItem)
        except DuplicateEntryException :
            def find():
                return self.__itemRepository.findDerivedItemByOriginalItemIdSizeAndFormat(original_item.id, transformationRequest.size, transformationRequest.targetFormat)
            self.__waitForItemStatusOk(find)
            derivedItem = find()
            
        try:
            img = Image.open(self.__absoluteOriginalFilename(original_item))
        except IOError, ex: 
            raise imgengine.ImageProcessingException(ex)
        
        if transformationRequest.size == img.size and transformationRequest.target_format.upper() == img.format.upper():
            try:
                shutil.copyfile(self.__absoluteOriginalFilename(original_item), cached_filename)
            except IOError, ex:
                raise imgengine.ImageProcessingException(ex)
        else:   
            target_image = ImageOps.fit(image=img, 
                                        size=transformationRequest.size, 
                                        method=Image.ANTIALIAS,
                                        centering=(0.5,0.5)) 
            try:
                target_image.save(cached_filename)
            except IOError, ex:
                raise imgengine.ImageProcessingException(ex)
        
        derivedItem.status = domain.STATUS_OK
        self.__itemRepository.update(derivedItem)
        
        return relative_cached_filename
    
    def _cleanupInconsistentItems(self):
        def cleanup_in_session(fetch_items, delete_file):
            items = fetch_items()
            for i in items:
                delete_file(i)
                self.__itemRepository.delete(i)
            
        def main_loop(has_more_items, fetch_items, delete_file):
            def callback(session):
                cleanup_in_session(fetch_items, delete_file)
            while has_more_items():
                self.__persistenceProvider.session_template().do_with_session(callback)
        
        def cleanup_derived_items():
            def delete_file(item):
                os.remove(self.__absoluteCachedFilename(item))
            main_loop(lambda: len(self.__itemRepository.findInconsistentDerivedItems(1)) > 0,
                      lambda: self.__itemRepository.findInconsistentDerivedItems(), 
                      delete_file)
        
        def cleanup_original_items():
            def delete_file(item):
                os.remove(self.__absoluteOriginalFilename(item))
            main_loop(lambda: len(self.__itemRepository.findInconsistentOriginalItems(1)) > 0,
                      lambda: self.__itemRepository.findInconsistentOriginalItems(), 
                      delete_file)
            
        cleanup_derived_items()
        cleanup_original_items()
        
    def __drop_data(self):
        self.__persistenceProvider.drop_all_tables()
        if os.path.exists(self.__dataDirectory):
            shutil.rmtree(self.__dataDirectory)
    
    def __init_directories(self):
        if not os.path.exists(self.__dataDirectory):
            os.makedirs(self.__dataDirectory)
        for directory in \
            [self.__absoluteCacheDirectory(), self.__absoluteOriginalDirectory()]:
            if not os.path.exists(directory):
                os.makedirs(directory)    
    def __init_data(self):
        self.__init_directories()
        self.__persistenceProvider.createOrUpgradeSchema()