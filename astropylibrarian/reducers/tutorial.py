# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Reduce the HTML source of a learn.astropy tutorial page (notebook-based)
into search records.
"""

__all__ = ('ReducedTutorial',)

from typing import List
from urllib.parse import urljoin

import lxml.html

from .utils import iter_sphinx_sections, Section


class ReducedTutorial:
    """A reduction of a notebook-based learn.astropy tutorial page into search
    records.

    Parameters
    ----------
    html_source : str
        The HTML source of the tutorial page.
    url : str
        The canonical URL of the tutorial page.
    """

    @property
    def url(self) -> str:
        """The canonical URL of the tutorial page.
        """
        return self._url

    @property
    def h1(self) -> str:
        """The tutorial's H1 headline text.
        """
        return self._h1

    @property
    def authors(self) -> List[str]:
        """The names of authors declared by the tutorial page.
        """
        return self._authors

    @property
    def keywords(self) -> List[str]:
        """The keywords declared by the tutorial page.
        """
        return self._keywords

    @property
    def summary(self) -> str:
        """The tutorial's summary paragraph.
        """
        return self._summary

    @property
    def images(self) -> List[str]:
        """The URLs of images in the tutorial content.
        """
        return self._images

    @property
    def sections(self) -> List[Section]:
        """The sections (`astropylibrarian.reducers.utils.Section`) that
        are found within the content.
        """
        return self._sections

    def __init__(self, *, html_source: str, url: str):
        self._url = url
        self._h1: str = ''
        self._authors: List[str] = []
        self._keywords: List[str] = []
        self._summary = ''
        self._images: List[str] = []
        self._sections: List["Section"] = []

        # These are headings for sections that should be ignored because
        # they're part of the metadata.
        self.ignored_headings = set(['authors', 'keywords', 'summary'])

        self._process_html(html_source)

    def _process_html(self, html_source: str):
        doc = lxml.html.document_fromstring(html_source)

        try:
            self._h1 = self._get_section_title(doc.cssselect('h1')[0])
        except IndexError:
            pass

        try:
            authors_paragraph = doc.cssselect('.card .section p')[0]
            self._authors = self._parse_comma_list(authors_paragraph)
        except IndexError:
            pass

        try:
            keywords_paragraph = doc.cssselect('#keywords p')[0]
            self._keywords = self._parse_comma_list(keywords_paragraph)
        except IndexError:
            pass

        try:
            summary_paragraph = doc.cssselect('#summary p')[0]
            self._summary = summary_paragraph.text_content().replace('\n', ' ')
        except IndexError:
            pass

        image_elements = doc.cssselect('.card .section img')
        for image_element in image_elements:
            img_src = image_element.attrib['src']
            self._images.append(urljoin(self.url, img_src))

        root_section = doc.cssselect('.card .section')[0]
        for s in iter_sphinx_sections(
                base_url=self._url,
                root_section=root_section,
                headers=[],
                header_callback=lambda x: x.rstrip('¶'),
                content_callback=lambda x: x.strip()):
            if not self._is_ignored_section(s):
                self._sections.append(s)

        # Also look for additional h1 section on the page.
        # Technically, the page should only have one h1, and all content
        # should be subsections of that. In real life, though, it's easy
        # to accidentally use additional h1 eleemnts for subsections.
        h1_heading = self._sections[-1].headings[-1]
        for sibling in root_section.itersiblings(tag='div'):
            if 'section' in sibling.classes:
                for s in iter_sphinx_sections(
                        root_section=sibling,
                        base_url=self._url,
                        headers=[h1_heading],
                        header_callback=lambda x: x.rstrip('¶'),
                        content_callback=lambda x: x.strip()
                        ):
                    if not self._is_ignored_section(s):
                        self._sections.append(s)

    def _is_ignored_section(self, section: Section) -> bool:
        """Determine if a section should be ignored.

        Uses the `ignored_headings` attribute to determine if a section should
        be ignored.

        Returns
        -------
        bool
            `True` if the section should be ignored; `False` if it should be
            accepted.
        """
        section_headings = set([h.lower() for h in section.headings])
        if section_headings.intersection(self.ignored_headings):
            return True
        else:
            return False

    @staticmethod
    def _get_section_title(element: lxml.html.HtmlElement) -> str:
        return element.text_content().rstrip('¶')

    @staticmethod
    def _parse_comma_list(element: lxml.html.HtmlElement) -> List[str]:
        content = element.text_content()
        return [s.strip() for s in content.split(',')]
