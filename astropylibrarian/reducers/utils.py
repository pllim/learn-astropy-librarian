# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""Utilities for reducing HTML pages into search records.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Generator, List, Optional

if TYPE_CHECKING:
    import lxml.html

__all__ = ["Section", "iter_sphinx_sections", "iter_nbcollection_sections"]

logger = logging.getLogger(__name__)


_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")


@dataclass
class Section:
    """A section of content."""

    content: str
    """The plain-text content of the section.
    """

    headings: List[str]
    """The section headers, ordered by hierarchy.

    The header of the present section is the last element.
    """

    url: str
    """The URL of this section (typically an anchor link).
    """

    @property
    def header_level(self) -> int:
        """The heading level of this section.

        For example, ``1`` corresponds to an "H1" section.
        """
        return len(self.headings)

    def new_section(self, *, tag: str, header: str, url: str) -> Section:
        new_level = int(tag[1])  # turn e.g. h1 into 1
        if new_level > self.header_level:
            new_headers = self.headings + [header]
        else:
            new_headers = self.headings[: new_level - 1] + [header]
        return Section(content="", headings=new_headers, url=url)


def iter_sphinx_sections(
    *,
    root_section: "lxml.html.HtmlElement",
    base_url: str,
    headers: List[str],
    header_callback: Optional[Callable[[str], str]] = None,
    content_callback: Optional[Callable[[str], str]] = None,
) -> Generator[Section, None, None]:
    """Iterate through the hierarchical sections in a root HTML element,
    yielding the content between that section header and the next section
    header.

    This class is designed specifically for Sphinx-generated HTML, where
    ``div.section`` or ``section`` elements to contain each hierarchical
    section of content.

    Parameters
    ----------
    root_section : lxml.html.HtmlElement
        The root HTML element. It should begin with the highest level of
        heading hierarchy, which is usually the "h1" header.
    base_url : str
        The URL of the HTML page itself.
    headers : list of str
        The ordered list of heading titles at hierarchical levels above the
        present section. This parameter should be an empty list for the
        *first* (h1) section.
    header_callback : callable
        This callback function processes the section title. The callable takes
        a string and returns a string.
    content_callback : callable
        This callback function processes the section content. The callable
        takes a string and returns a string.

    Yields
    ------
    section : Section
        Yields `Section` objects for each section segment. Sections are yielded
        depth-first. The top-level section is yielded last.
    """
    id_ = root_section.attrib["id"]
    url = f"{base_url}#{id_}"
    text_elements: List[str] = []
    for element in root_section:
        if element.tag in _HEADING_TAGS:
            current_header = element.text_content()
            if header_callback:
                current_header = header_callback(current_header)
            current_headers = headers + [current_header]
        elif (element.tag == "section") or (
            element.tag == "div" and "section" in element.classes
        ):
            yield from iter_sphinx_sections(
                root_section=element,
                base_url=base_url,
                headers=current_headers,
                header_callback=header_callback,
                content_callback=content_callback,
            )
        else:
            # To modify this element to extract content from it
            # To extract content from this element we may need to modify it
            # We don't want to affect the whole document tree though, so
            # we make this temporary copy.
            content_element = deepcopy(element)

            # Delete "cell_output" divs, which are the code outputs from
            # Jupyter-based pages (Jupyter Notebook). The outputs can be large
            # and are often less relevant.
            try:
                output_divs = content_element.find_class("cell_output")
                for output_div in output_divs:
                    output_div.drop_tree()
            except ValueError:
                # Raised because "HtmlComment" element does not support
                # find_class().
                pass

            # Get plain-text content of the section
            try:
                if content_callback:
                    text_elements.append(
                        content_callback(content_element.text_content())
                    )
                else:
                    text_elements.append(content_element.text_content())
            except ValueError:
                logger.debug("Could not get content from %s", content_element)
                continue

    yield Section(
        content="\n\n".join(text_elements), headings=current_headers, url=url
    )


def iter_nbcollection_sections(
    *,
    root_element: "lxml.html.HtmlElement",
    base_url: str,
    header_callback: Optional[Callable[[str], str]] = None,
    content_callback: Optional[Callable[[str], str]] = None,
) -> Generator[Section, None, None]:
    current_section = Section(content="", headings=[], url="")

    for content_element in iter_nbcollection_content_elements(
        root_element=root_element,
        base_url=base_url,
        header_callback=header_callback,
        content_callback=content_callback,
    ):
        if content_element.tag in _HEADING_TAGS:
            # A new heading can trigger a new section.
            # First yield the current content if it already has content
            if current_section.headings and current_section.content:
                yield current_section

            # Now reset the content stack
            header_id = ""
            if "id" in content_element.attrib.keys():
                header_id = content_element.attrib["id"]
            if header_callback:
                header_content = header_callback(
                    content_element.text_content()
                )
            else:
                header_content = content_element.text_content()

            current_section = current_section.new_section(
                tag=content_element.tag,
                header=header_content,
                url=f"{base_url}#{header_id}",
            )
        else:
            # Accumulate content into the current stack
            if content_callback:
                current_section.content += (
                    f" {content_callback(content_element.text_content())}"
                )
            else:
                current_section.content += f" {content_element.text_content()}"

    if current_section.headings:
        yield current_section


def iter_nbcollection_content_elements(
    *,
    root_element: lxml.html.HtmlElement,
    base_url: str,
    header_callback: Optional[Callable[[str], str]] = None,
    content_callback: Optional[Callable[[str], str]] = None,
) -> Generator[lxml.html.HtmlElement, None, None]:
    for element in root_element:
        if "jp-RenderedHTMLCommon" in root_element.classes:
            for child_element in element:
                yield element
        elif "CodeMirror" in root_element.classes:
            yield element
        elif element.tag == "div":
            yield from iter_nbcollection_content_elements(
                root_element=element,
                base_url=base_url,
                header_callback=header_callback,
                content_callback=content_callback,
            )
        else:
            continue
