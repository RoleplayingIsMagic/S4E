#!/usr/bin/env python3
# Google Docs automake tool, for Roleplaying is Magic's Season Four Web Edition

#FIX: split up parts
#FIX: split up sections in certain (really large) parts?
#FIX: parts and implicit images and ways to circuimvent that

# configuration
name = 'Roleplaying is Magic: S4E'
base_site_dir = 'base_site'
output_dir = 'output'
output_page = output_dir + '/{ident}.html'

base_page_html = open('template.html', 'r').read()

# importing

import os
import sys
import codecs
from titlecase import titlecase

if not os.path.exists(output_dir):
    os.makedirs(output_dir)


# Setup tinycss, our css parser
#
import tinycss
css_parser = tinycss.make_parser('page3')


# pyquery/lxml (pq/lx) objects for simplicity
#
# We should probably create a class that provides a simplified interface to both lxml and pq's
# attributes from a single, unified object, but that's a little overkill for this project right now
from pyquery import PyQuery as pq
import lxml.html


def lx(element):
    """Return a given element as an lxml element."""
    if type(element) == lxml.html.HtmlElement:
        return element
    elif type(element) == pq:
        return lxml.html.fragments_fromstring(element.__html__())[0]
    elif type(element) == str:
        return lxml.html.fragments_fromstring(element)[0]


# Custom tree copier, modified from shutil.copytree source
#
# This version /merges/ directories, when the destination directory already exists
# Really, that's the only change at all
#
# Yes, Python really doesn't just have it as a function argument
#
# I know, right?
#
import shutil


def copytree(src, dst, symlinks=False):
    """ Merge """
    names = os.listdir(src)
    os.makedirs(dst, exist_ok=True)
    errors = []
    for name in names:
        # if name[0] == '_':
        #     continue
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)
        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname):
                copytree(srcname, dstname, symlinks)
            else:
                shutil.copy2(srcname, dstname)
            # XXX What about devices, sockets etc.?
        except OSError as why:
            errors.append((srcname, dstname, str(why)))
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Exception as err:
            errors.extend(err.args[0])
    try:
        shutil.copystat(src, dst)
    except WindowsError:
        # can't copy file access times on Windows
        pass
    except OSError as why:
        errors.extend((src, dst, str(why)))
    if errors:
        raise Exception(errors)


# Google Doc

# Parsing and keeping track of our base Google Doc
#
class google_document:
    """Parses a Google Doc HTML file into a nice usable format for us."""

    def __init__(self, title, maker, debug=False):
        self.title = title
        self.maker = maker
        self.debug = debug

    def parse(self, doc_html):
        """Parse a given html document."""
        self.pq = pq(doc_html)

        ## Separating out bold/italic/underlined tags
        self.tags = {}

        css = css_parser.parse_stylesheet(self.pq('style').html())
        selectors = [
            ('font-weight', 'bold'),
            ('font-style', 'italic'),
            ('text-decoration', 'underline'),
            ('text-align', 'center'),
            ('text-align', 'right'),
        ]

        for rule in css.rules:

            # only check classes
            if hasattr(rule, 'selector') and rule.selector[0].type == 'DELIM':
                class_name = rule.selector[1].as_css()

                for declaration in rule.declarations:
                    rule_name = declaration.name
                    rule_value = declaration.value.as_css()

                    rule_tuple = (rule_name, rule_value)

                    if rule_tuple in selectors:
                        if rule_value not in self.tags:
                            self.tags[rule_value] = []
                        self.tags[rule_value].append(class_name)

        ## Give us our outline
        book_started = False
        for child in self.pq('body').children():
            text = titlecase(pq(child).text())

            # we need to wait for the book marker so we can start the book
            if text == '*****************************************************************':
                book_started = True
                continue

            if not book_started:
                continue  # book not started yet, continue 'til we find the start marker

            header_html = ''
            if pq(child).hasClass('title') or lx(child).tag in ['h1', 'h2', 'h3', 'h4']:
                ignore_tags = ['bold']
                if lx(child).tag == 'h4':
                    ignore_tags.append('italic')

                # classes
                properties = {
                    'bold': False,
                    'italic': False,
                    'underline': False,
                    'center': False,
                    'right': False,
                }
                if pq(child).attr('class'):
                    for html_class in pq(child).attr('class').split():
                        for tag_type in self.tags:
                            if tag_type in ['center', 'right']:
                                if html_class in self.tags[tag_type]:
                                    properties[tag_type] = True

                align = None
                if properties['center']:
                    align = 'center'
                elif properties['right']:
                    align = 'right'

                header_html = self.parse_element(pq(pq(child).html()), ignore_tags=ignore_tags, title=True)

            # variables
            sec_image = True
            if '&NoImage' in header_html:
                sec_image = False
                header_html = header_html.replace('&NoImage', '')

            sec_split_sections = True
            if '&NoSplitSections' in header_html:
                sec_split_sections = False
                header_html = header_html.replace('&NoSplitSections', '')

            # actual parsing
            if pq(child).hasClass('title') or lx(child).tag == 'h1':  # part
                self.maker.add_part(header_html, image=sec_image, split_sections=sec_split_sections, align=align)

            elif lx(child).tag == 'h2':  # section
                self.maker.add_section(header_html, image=sec_image, align=align)

            elif lx(child).tag == 'h3':  # subsection
                self.maker.add_subsection(header_html, align=align)

            elif lx(child).tag == 'h4': # sidebar
                if pq(child).text() == '---':
                    self.maker.finish_sidebar()
                else:
                    if header_html == ' Sidebar':  # empty
                        header_html = ''
                    self.maker.start_sidebar(header_html, align=align)

            else:
                self.maker.add_content(self.parse_element(child))

    def parse_element(self, element, ignore_tags=[], title=False, align=None):
        """Parse a single element and return our HTML for it."""
        if type(element) in [str, lxml.etree._ElementUnicodeResult]:
            return element.replace('\xa0', '&nbsp;')

        # classes
        properties = {
            'bold': False,
            'italic': False,
            'underline': False,
            'center': False,
            'right': False,
        }

        if pq(element).attr('class'):
            for html_class in pq(element).attr('class').split():
                for tag_type in self.tags:
                    if tag_type not in ignore_tags:
                        if html_class in self.tags[tag_type]:
                            properties[tag_type] = True

        # align
        if align == 'center':
            properties['center'] = True
        elif align == 'right':
            properties['right'] = True

        # special ul class
        ul_header = True

        # either make our content str, or parse it to html
        new_html = ''
        for part in pq(element).contents():
            if type(part) in [str, lxml.etree._ElementUnicodeResult]:
                new_html += str(part)
            else:  # dodgy, but it works
                new_parsed_html = self.parse_element(part, ignore_tags=ignore_tags)
                if lx(element).tag == 'ul' and 'no_ul_header' in new_parsed_html:
                    ul_header = False
                else:
                    new_html += new_parsed_html

        new_html = new_html.replace('\xa0', '&nbsp;')

        # process tags without text before we kill them below
        if lx(element).tag in ['hr']:
            return '<{tag}>'.format(tag=lx(element).tag)

        # # we only care about tags with text after this
        if new_html.replace('&nbsp;', ' ').strip() == '':
            return ' '

        # return text, including html of any internal elements and such that we need to fix
        if lx(element).tag in ['span', 'p']:
            if title:  # VERY DODGY
                # we add the space here because it usually exists anyway, and HTML does quite
                #  like its random spaces and such to space words out >_>
                new_html = ' ' + titlecase(new_html.lstrip())

            # center/right align
            class_list = []
            
            # center-right align
            if properties['center']:
                class_list.append('center')
            elif properties['right']:
                class_list.append('right')

            # size shortcuts
            for size in ['tiny', 'small', 'regular', 'big', 'large', 'huge', 'kaushan']:
                size_string = '&{}'.format(size)
                if size_string in new_html:
                    new_html = new_html.replace(size_string, '')
                    class_list.append(size)

            if len(class_list) > 0:
                classes = ' class="{}"'.format(' '.join(class_list))
            else:
                classes = ''

            # tags and such
            if properties['italic']:
                new_html = '<em>{}</em>'.format(new_html)
            if properties['bold']:
                new_html = '<strong>{}</strong>'.format(new_html)

            if lx(element).tag == 'p':
                new_html = '<p{}>{}</p>'.format(classes, new_html)
            elif classes != '':
                new_html = '<span{}>{}</span>'.format(classes, new_html)

            return new_html

        elif lx(element).tag in ['a']:
            if pq(element).attr('href'):
                if new_html == 'RoleplayingIsMagic.com':
                    link = 'http://roleplayingismagic.com'
                elif new_html == 'TallTailTellsTales@gmail.com':
                    link = 'mailto:TallTailTellsTales@gmail.com'
                elif new_html == 'S4E Character Sheet':
                    link = '{{ page.rootdir }}/cl/S4E Character Sheet.pdf'
                else:
                    link = pq(element).attr('href')
                return '<{tag} href="{href}">{}</{tag}>'.format(new_html, tag=lx(element).tag, href=link)
            else:
                return new_html

        elif lx(element).tag in ['ul']:
            if ul_header:
                return '<{tag} class="with_header">{}</{tag}>'.format(new_html, tag=lx(element).tag)
            else:
                return '<{tag} class="no_header">{}</{tag}>'.format(new_html, tag=lx(element).tag)

        elif lx(element).tag in ['li', 'td', 'tr', 'tbody', 'ol', 'ul', 'table']:
            return '<{tag}>{}</{tag}>'.format(new_html, tag=lx(element).tag)

        else:
            print('tag is', lx(element).tag, pq(element).text()[:200], file=sys.stderr)
            exit(1)

# Content types
class content_base:
    """Base content type."""
    HAS_CONTENT = True
    def __init__(self, name=None):
        if self.HAS_CONTENT:
            self.content = []
        self.name = []
        self.part = 0
        self.section = 0
        self.subsection = 0
        self.sidebar = 0
        self.header_align = None
        if name is not None:
            self.add_name(name)
    def _add_content(self, content_store, new_content):
        """Add new_content to the given content_store."""
        if len(content_store) > 0 and type(new_content) == type(content_store[-1]) == str:
            content_store[-1] += '\n' + new_content
        else:
            content_store.append(new_content)
        return content_store
    def _content_html(self, content_store):
        """Return the output HTML for given content store"""
        output = ''
        for item in content_store:
            if isinstance(item, str):
                output += item
            else:
                if not isinstance(item, new_page_types):
                    output += item.html()
        return output
    def _header_classes(self):
        """Returns the classes for our header (parts, sections, etc)."""
        if self.header_align is not None:
            return ' class="{}"'.format(self.header_align)
        return ''
    def add_name(self, new_content):
        """Add content to our name."""
        self._add_content(self.name, new_content)
    def add_content(self, new_content):
        """Add content to our content store."""
        self._add_content(self.content, new_content)
    def ident(self):
        """Identifier for this content item."""
        if self.subsection != 0:
            identifier = 'p{}.s{}.s{}'.format(self.part, self.section, self.subsection)
        elif self.section != 0:
            identifier = 'p{}.s{}'.format(self.part, self.section)
        else:
            identifier = 'p{}'.format(self.part)
        return identifier

class part_c(content_base):
    """Part content."""
    HAS_CONTENT = True
    def html(self):
        """Return HTML for this object."""
        header_image = ''
        if self.image:
            header_image = '<img class="part-header" src="{{{{ page.rootdir }}}}/cl/img/parts/p{part}.jpg" />'.format(part=self.part)

        # return '''{image}<h1 name="p{part}"{class}>{name}</h1> {content}'''.format(**{
        if self._content_html(self.name).strip() == 'Front Cover':
            base_str = '''{image}{content}'''
        else:
            base_str = '''{image}<h1 class="large center strong kaushan" name="p{part}"{class}>{name}</h1> {content}'''
        return base_str.format(**{
            'part': self.part,
            'image': header_image,
            'name': self._content_html(self.name),
            'class': self._header_classes(),
            'content': self._content_html(self.content),
        })

class section_c(content_base):
    """Section content."""
    HAS_CONTENT = True
    def html(self):
        """Return HTML for this object."""
        return '''<h2 name="p{part}-{section}"{class}>{name}</h2> {content}'''.format(**{
            'part': self.part,
            'section': self.section,
            'name': self._content_html(self.name),
            'class': self._header_classes(),
            'content': self._content_html(self.content),
        })

class subsection_c(content_base):
    """Subsection content."""
    HAS_CONTENT = True
    def html(self):
        """Return HTML for this object."""
        return '''<h3 name="p{part}-{section}-{subsection}"{class}>{name}</h3> {content}'''.format(**{
            'part': self.part,
            'section': self.section,
            'subsection': self.subsection,
            'name': self._content_html(self.name),
            'class': self._header_classes(),
            'content': self._content_html(self.content),
        })

class sidebar_c(content_base):
    """Sidebar content."""
    HAS_CONTENT = True
    def html(self):
        """Return HTML for this object."""
        return '''<div class="sidebar" name="p{part}-{section}-{subsection}-{sidebar}"><h3{class}>{name}</h3> {content}</div>'''.format(**{
            'part': self.part,
            'section': self.section,
            'subsection': self.subsection,
            'sidebar': self.sidebar,
            'name': self._content_html(self.name),
            'class': self._header_classes(),
            'content': self._content_html(self.content),
        })

# File output
new_page_types = (part_c, section_c)  # content types we make a new page for


class toc_file:
    """Simple little file to store our table of contents."""
    def __init__(self, path, title=None):
        """Open everything"""
        self._file = open(path, 'w')

        self._write('<h1>Table of Contents</h1>\n')

    def close(self):
        """Close everything."""
        self._write('\n')
        self._file.close()

    def _write(self, string_to_write):
        """Write a string to the output file."""
        self._file.write(string_to_write)

    def add_part(self, part_name, ident):
        # lazy and dodgy, but it works
        if part_name == 'Front Cover':
            ident = 'index'
        self._write('<a href="{{{{ page.rootdir }}}}/{ident}.html" class="toc_part">{name}</a>\n'.format(name=part_name, ident=ident))

    def add_section(self, section_name, ident):
        self._write('<a href="{{{{ page.rootdir }}}}/{ident}.html" class="toc_section">{name}</a>\n'.format(name=section_name, ident=ident))

    def add_subsection(self, subsection_name, ident):
        self._write('<a href="{{{{ page.rootdir }}}}/{ident}.html" class="toc_subsection">{name}</a>\n'.format(name=subsection_name, ident=ident))

    # def add_sidebar(self, sidebar_name):
    #     self._write('      # {}\n'.format(sidebar_name))


# pages
class html_page:
    """HTML Page for S4E."""
    def __init__(self, part, section=None, name='', filename=None):
        self.part = part
        self.section = section
        self.name = name
        self.filename = filename
        self.html = ''
        self.previous_page = None
        self.next_page = None

    def _filename(self):
        """Generate filename for this page."""
        # explicit filename
        if self.filename is not None:
            return self.filename

        # autogenerated filename
        else:
            if self.section is not None:
                return '{}-{}.html'.format(self.part, self.section)
            else:
                return '{}.html'.format(self.part)

    def add_html(self, html):
        """Add HTML to this page."""
        self.html += html


# our stuff
def toc_links(toc, toc_i):
    """Given our toc list structure, return the current, previous, and next links for the given item. Convoluded."""
    prev = None
    if (toc_i - 1) > -1:
        prev = toc[toc_i - 1][1]

    curr = None
    if len(toc) > toc_i:
        curr = toc[toc_i][1]

    next = None
    if len(toc) > (toc_i + 1):
        next = toc[toc_i + 1][1]

    return prev, curr, next


def page_to_colour(page_part):
    """Page part to colour."""
    if page_part in [1, 2, 11, 'single']:
        return 'green'
    elif page_part in [3, 4, 12]:
        return 'blue'
    elif page_part in [10]:
        return 'darkblue'
    elif page_part in [5, 6]:
        return 'pink'
    elif page_part in [7]:
        return 'purple'
    elif page_part in [8, 9]:
        return 'orange'
    else:
        return 'default'


class s4e_maker:
    """S4E Make Class."""
    def __init__(self, name):
        self.name = name
        self.toc = toc_file('base_site/_includes/toc.html', self.name)
        self.content_tree = []
        self.part = 0
        self.section = 0
        self.subsection = 0
        self.sidebar = 0
        self.depth = 0

    def output_page(self, base_content_item, page_content):
        """Output the selected page."""

    def shutdown(self):
        """Shutdown everything."""
        toc = []  # table of contents
        toc_i = 0  # which toc element we're currently on/retrieving

        # construct toc
        new_subpages = True
        for content_item in self.content_tree:
            if isinstance(content_item, new_page_types):
                toc.append([content_item.name[0].strip(), content_item.ident().replace('.', '-')])
            if content_item.split_sections:
                for item in content_item.content:
                    if isinstance(item, new_page_types):
                        toc.append([item.name[0].strip(), item.ident().replace('.', '-')])
        toc.append(['Single Page Version', 'single'])

        toc[0] = ['Front Cover', 'index']  # we need an index page guize

        # output
        base_new_page_buffer = {
            'item': None,  # actual item, part_c, etc
            'content': '',  # html
            'prev': None,  # previous toc link
            'curr': None,  # current toc link
            'next': None,  # next toc link
        }
        new_page_buffer = None


        def new_page_if_required(curr_item, force_new_page=False):
            """Outputs a new page if required."""
            if isinstance(curr_item, new_page_types) or force_new_page:
                # this affects things outside this function's scope
                nonlocal self
                nonlocal toc_i
                nonlocal new_page_buffer

                prev, curr, next = toc_links(toc, toc_i)
                toc_i += 1
                
                if new_page_buffer is not None:
                    output_filename = output_page.format(ident=new_page_buffer['curr'])

                    if isinstance(new_page_buffer['item'], part_c):
                        toc_func = self.toc.add_part
                    elif isinstance(new_page_buffer['item'], section_c):
                        toc_func = self.toc.add_section
                    elif isinstance(new_page_buffer['item'], subsection_c):
                        toc_func = self.toc.add_subsection
                    else:
                        toc_func = None

                    if toc_func is not None:
                        toc_func(new_page_buffer['item'].name[0].strip().replace('&', '&amp;'), new_page_buffer['item'].ident().replace('.', '-'))

                    with open(output_filename, 'w') as out:
                        out.write(base_page_html.format(**{
                            'ident': new_page_buffer['item'].ident(),
                            'name': new_page_buffer['item'].name[0].strip(),
                            'content': new_page_buffer['content'],
                            'colour': new_page_buffer['colour'],
                            'part': new_page_buffer['item'].part,
                            'section': new_page_buffer['item'].section,
                            'prev': new_page_buffer['prev'],
                            'curr': new_page_buffer['curr'],
                            'next': new_page_buffer['next'],
                        }))

                # reset new page buffer
                new_page_buffer = base_new_page_buffer
                new_page_buffer['item'] = curr_item
                new_page_buffer['colour'] = page_to_colour(curr_item.part)
                new_page_buffer['prev'] = prev
                new_page_buffer['curr'] = curr
                new_page_buffer['next'] = next
                new_page_buffer['content'] = curr_item.html()

                if isinstance(curr_item, part_c) and not curr_item.split_sections:
                    for item in curr_item.content:
                        if isinstance(item, content_base):
                            new_page_buffer['content'] += item.html()

            else:
                if isinstance(curr_item, content_base):
                    new_page_buffer['content'] += curr_item.html()
                # elif isinstance(curr_item, str):
                #     new_page_buffer['content'] += curr_item

        for content_item in self.content_tree:
            new_page_if_required(content_item)
            if content_item.split_sections:
                for item in content_item.content:
                    new_page_if_required(item)

        new_page_if_required(self.content_tree[-1], force_new_page=True)  # force last page

        # add a last page with everything on it, to be used for printing
        output_filename = output_page.format(ident='single')
        
        single_page_content = ''
        for content_item in self.content_tree:
            single_page_content += content_item.html()
            for item in content_item.content:
                if isinstance(item, content_base):
                    single_page_content += item.html()
                # elif isinstance(item, str):
                #     single_page_content += item

        prev, curr, next = toc_links(toc, toc_i - 1)
        with open(output_filename, 'w') as out:
            out.write(base_page_html.format(**{
                'ident': 'single',
                'name': 'Single Page',
                'content': single_page_content,
                'colour': 'green',
                'part': 'single',
                'section': 0,
                'prev': prev,
                'curr': curr,
                'next': next,
            }))

        from pprint import pprint
        pprint(toc)

        self.toc.add_part('Single Page Version (for print)', 'single')
        self.toc.close()

    def add_part(self, part_name, image=False, split_sections=True, align=None):
        """Add the given part"""
        self.depth = 1

        # reset
        self.part += 1
        self.section = 0
        self.subsection = 0

        # new item
        new_part = part_c(part_name)
        new_part.part = self.part
        new_part.image = image
        new_part.split_sections = split_sections
        new_part.header_align = align

        self.content_tree.append(new_part)

    def add_section(self, section_name, image=False, align=None):
        """Add the given section."""
        self.depth = 2

        # reset
        self.section += 1
        self.subsection = 0

        # new section
        new_section = section_c(section_name)
        new_section.part = self.part
        new_section.section = self.section
        new_section.image = image
        new_section.header_align = align

        self.content_tree[-1].add_content(new_section)

    def add_subsection(self, subsection_name, align=None):
        """Add the given subsection."""
        self.depth = 3

        # reset
        self.subsection += 1

        # new subsection
        new_subsection = subsection_c(subsection_name)
        new_subsection.part = self.part
        new_subsection.section = self.section
        new_subsection.subsection = self.subsection
        new_subsection.header_align = align

        self.content_tree[-1].content[-1].add_content(new_subsection)

    def start_sidebar(self, sidebar_name, align=None):
        """Add the given sidebar."""
        self.depth += 1

        # reset
        self.sidebar += 1

        # new sidebar
        new_sidebar = sidebar_c(sidebar_name)
        new_sidebar.part = self.part
        new_sidebar.section = self.section
        new_sidebar.subsection = self.subsection
        new_sidebar.sidebar = self.sidebar
        new_sidebar.header_align = align

        item = self.content_tree[-1]
        for depth_level in range(1, self.depth-1):
            item = item.content[-1]
        item.add_content(new_sidebar)

    def finish_sidebar(self):
        """Finish the current sidebar."""
        self.depth -= 1

    def add_content(self, content):
        """Add content, generic HTML."""
        item = self.content_tree[-1]
        for depth_level in range(1, self.depth):
            item = item.content[-1]
        item.add_content(content)

# actually run everything!
maker = s4e_maker(name)
gdoc = google_document(name, maker)
with open('master_doc.html', 'r') as master_doc:
    gdoc.parse(master_doc.read())

maker.shutdown()
copytree(base_site_dir, output_dir)
