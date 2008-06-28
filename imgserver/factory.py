import os
from imgserver import imgengine, security, persistence
from imgserver.imgengine.transformationrequest import TransformationRequest
from imgserver.imgengine.imagerequestprocessor import ImageRequestProcessor
from imgserver.imgengine.imagerequestprocessor import IImageRequestProcessor
from imgserver.persistence.persistenceprovider import PersistenceProvider
from imgserver.persistence.itemrepository import ItemRepository

class ImageServerFactory(object):
 
    def __init__(self):
        super(ImageServerFactory, self)
        self.__persistenceProvider = None
        self.__itemRepository = None
        self.__imageProcessor = None

    def getPersistenceProvider(self):
        return self.__persistenceProvider


    def getItemRepository(self):
        return self.__itemRepository


    def getImageProcessor(self):
        return self.__imageProcessor

    def createImageServer(self,data_directory, dbstring, allowed_sizes):
        if not os.path.exists(data_directory):
            os.makedirs(data_directory)
        
        self.__persistenceProvider = PersistenceProvider(dbstring)
        self.__persistenceProvider.createOrUpgradeSchema()
        
        self.__itemRepository = ItemRepository(self.__persistenceProvider)
        
        self.__imageProcessor = IImageRequestProcessor(ImageRequestProcessor(self.__itemRepository, self.__persistenceProvider, data_directory))
        self.__imageProcessor.prepareTransformation =  security.imageTransformationSecurityDecorator(allowed_sizes)(self.__imageProcessor.prepareTransformation)
        
        self.__imageProcessor.cleanupInconsistentItems()
        return self.__imageProcessor
    
    persistenceProvider = property(getPersistenceProvider, None, None, "PersistenceProvider's Docstring")
    itemRepository = property(getItemRepository, None, None, "ItemRepository's Docstring")
    imageProcessor = property(getImageProcessor, None, None, "ImageProcessor's Docstring")
