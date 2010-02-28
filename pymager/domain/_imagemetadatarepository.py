"""
    PyMager RESTful Image Conversion Service 
    Copyright (C) 2008 Sami Dalouche

    This file is part of PyMager.

    PyMager is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    PyMager is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with PyMager.  If not, see <http://www.gnu.org/licenses/>.

"""

from zope.interface import Interface, implements
from pymager.domain._abstractimagemetadata import AbstractImageMetadata
from pymager.domain._originalimagemetadata import OriginalImageMetadata
from pymager.domain._derivedimagemetadata import DerivedImageMetadata


class DuplicateEntryException(Exception):
    """Thrown when errors happen while processing images """
    def __init__(self, duplicate_id):
        self.__duplicate_id = duplicate_id
        Exception.__init__(self, 'Duplicated ID: %s' % duplicate_id)

    def get_duplicate_id(self):
        return self.__duplicate_id
    
    duplicate_id = property(get_duplicate_id, None, None, "The ID that led to the DuplicateEntryException")

class ImageMetadataRepository(Interface):
    """ DDD repository for Original and Derived Items """
    def find_original_image_metadata_by_id(self, image_id):
        """ Find an OriginalImageMetadata by its ID """
    
    def find_inconsistent_original_image_metadatas(self, maxResults=100):
        """ Find Original Items that are in an inconsistent state """
    
    def find_inconsistent_derived_image_metadatas(self, maxResults=100):
        """ Find Derived Items that are in an inconsistent state """
    
    def find_derived_image_metadata_by_original_image_metadata_id_size_and_format(self, image_id, size, format):
        """ Find Derived Items By :
            - the Original Item ID
            - the size of the Derived Item
            - the format of the Derived Item """
    def add(self, item):
         """ Create a persistent instance of an item
             @raise DuplicateEntryException: when an item with similar characteristics has already been created   
         """
    def delete(self, item):
        """ Deletes an item, and its children items, in the case of an original item that has
        several derived items based on it"""
