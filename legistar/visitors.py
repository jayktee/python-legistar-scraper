import io
import re
import contextlib
from urllib.parse import urlparse
from collections import defaultdict

import visitors
import visitors.ext.etree
from hercules import CachedAttr

from legistar.base.view import View
from legistar.base.field import FieldAggregator, FieldAccessor


class DetailVisitor(visitors.Visitor):
    '''Visits a detail page and collects all the displayed fields into a
    dictionary that maps label text to taterized DOM nodes.

    Effectively groups different elements and their attributes by the unique
    sluggy part of their verbose aspx id names. For example, the 'Txt' part
    of 'ctl00_contentPlaceholder_lblTxt'.
    '''
    # ------------------------------------------------------------------------
    # These methods customize the visitor.
    # ------------------------------------------------------------------------
    def __init__(self, config_obj):
        self.data = defaultdict(dict)
        self.config_obj = self.cfg = config_obj

    def finalize(self):
        '''Reorganize the data so it's readable labels (viewable on the page)
        are the dictionary keys, instead of the sluggy text present in their
        id attributes. Wrap each value in a DetailField.
        '''
        newdata = {}
        for id_attr, data in tuple(self.data.items()):
            alias = data.get('label', id_attr).strip(':')
            value = self.cfg.make_child(DetailField, data)
            newdata[alias] = value
            if alias != id_attr:
                newdata[id_attr] = value
        return newdata

    def get_nodekey(self, el):
        '''We're visiting a treebie-ized lxml.html document, so dispatch is
        based on the tag attribute.
        '''
        # The weird Comment tag.
        tag = el.tag
        if not isinstance(tag, str):
            raise self.Continue()
        return tag

    def get_children(self, el):
        return tuple(el)

    # ------------------------------------------------------------------------
    # The DOM visitor methods.
    # ------------------------------------------------------------------------
    def visit_a(self, el):
        attrib = el.attrib
        if 'id' not in attrib:
            return
        if 'href' not in attrib:
            return

        # If it's a field label, collect the text and href.
        matchobj = re.search(r'_hyp(.+)', attrib['id'])
        if matchobj:
            key = matchobj.group(1)
            data = self.data[key]
            data.update(url=attrib['href'], el=el)
            if 'label' not in data:
                label = el.text_content().strip(':')
                data['label'] = label
                raise self.Continue()
            return

    def visit_span(self, el):
        idattr = el.attrib.get('id')
        if idattr is None:
            return

        # If it's a label
        matchobj = re.search(r'_lbl(.+?)X', idattr)
        if matchobj:
            key = matchobj.group(1)
            label = el.text_content().strip(':')
            self.data[key]['label'] = label
            raise self.Continue()

        matchobj = re.search(r'_lbl(.+)', idattr)
        if matchobj:
            key = matchobj.group(1)
            self.data[key]['el'] = el
            return

        # If its a value
        matchobj = re.search(r'_td(.+)', idattr)
        if matchobj:
            key = matchobj.group(1)
            self.data[key]['el'] = el

    def visit_td(self, el):
        idattr = el.attrib.get('id')
        if idattr is None:
            return
        matchobj = re.search(r'_td(.+)', idattr)
        if matchobj is None:
            return
        key = matchobj.group(1)
        self.data[key]['el'] = el

