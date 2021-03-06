# coding: utf-8

import fcntl
import termios
import sys
import struct
import signal
import re
import os
import urwid
from selecta.widgets import (
    LineCountWidget, SearchEdit, ResultList, ItemWidgetPlain, ItemWidgetWords,
    ItemWidgetPattern)

# pylint: disable=line-too-long,unused-argument,too-many-nested-blocks
# pylint: disable=too-many-branches,no-self-use

if sys.version_info < (3, 0):
    sys.exit('Sorry, you need Python 3 to run this!')

palette = [
    ('head', '', '', '', '#000', '#618'),
    ('body', '', '', '', '#ddd', '#000'),
    ('focus', '', '', '', '#000', '#da0'),
    ('input', '', '', '', '#fff', '#618'),
    ('empty_list', '', '', '', '#ddd', '#b00'),
    ('pattern', '', '', '', '#f91', ''),
    ('pattern_focus', '', '', '', 'bold,#a00', '#da0'),
    ('line', '', '', '', '', ''),
    ('line_focus', '', '', '', '#000', '#da0'),
]

signal.signal(signal.SIGINT, lambda *_: sys.exit(0))  # die with style

HIGHLIGHT_NONE, HIGHLIGHT_WHOLE_STRING, HIGHLIGHT_WORDS, HIGHLIGHT_REGEX = range(4)


class Selector:
    def __init__(self, revert_order, remove_bash_prefix, remove_zsh_prefix, regexp, case_sensitive,
                 remove_duplicates, show_matches, infile):

        self.show_matches = show_matches
        self.regexp_modifier = regexp
        self.case_modifier = case_sensitive
        self.remove_bash_prefix = remove_bash_prefix

        self.lines = []

        if revert_order:
            lines = reversed(infile.readlines())
        else:
            lines = infile

        for line in lines:
            if remove_bash_prefix:
                # ^   21 command --> [21, command] --> command
                line = line.split(sep=None, maxsplit=1)[1].strip()

            if remove_zsh_prefix:
                line = re.split(r'\s+', line, maxsplit=4)[-1]

            #if 'selecta <(history)' not in line:
            if not remove_duplicates or line not in self.lines:
                self.lines.append(line)

        self.line_widgets = []

        self.line_count_display = LineCountWidget()
        self.search_edit = SearchEdit(edit_text='')

        self.modifier_display = urwid.Text('')

        urwid.connect_signal(self.search_edit, 'done', self.edit_done)
        urwid.connect_signal(self.search_edit, 'toggle_case_modifier', self.toggle_case_modifier)
        urwid.connect_signal(self.search_edit, 'toggle_regexp_modifier', self.toggle_regexp_modifier)
        urwid.connect_signal(self.search_edit, 'change', self.edit_change)

        header = urwid.AttrMap(
            urwid.Columns(
                [urwid.AttrMap(self.search_edit, 'input', 'input'),
                 self.modifier_display,
                 ('pack', self.line_count_display), ],
                dividechars=1, focus_column=0),
            'head', 'head')

        self.item_list = urwid.SimpleListWalker(self.line_widgets)
        self.listbox = ResultList(self.item_list)

        urwid.connect_signal(self.listbox, 'resize', self.list_resize)

        self.view = urwid.Frame(body=self.listbox, header=header)

        self.loop = urwid.MainLoop(self.view, palette, unhandled_input=self.on_unhandled_input)
        self.loop.screen.set_terminal_properties(colors=256)

        self.line_count_display.update(self.listbox.last_size, len(self.item_list))

        # TODO workaround, when update_list is called directly, the linecount widget gets not updated
        self.loop.set_alarm_in(0.01, lambda *loop: self.update_list(''))

        self.update_modifiers()
        self.loop.run()

    def list_resize(self, size):
        self.line_count_display.update(visible_lines=size[1])

    def toggle_case_modifier(self):
        self.case_modifier = not self.case_modifier
        self.update_modifiers()

    def toggle_regexp_modifier(self):
        self.regexp_modifier = not self.regexp_modifier
        self.update_modifiers()

    def update_modifiers(self):
        modifiers = [
            'regexp' if self.regexp_modifier else 'noregexp',
            'case' if self.case_modifier else 'nocase']
        self.modifier_display.set_text('[{}]'.format(','.join(modifiers)))

    def update_list(self, search_text):
        if search_text in ('', '"', '""'):  # show all lines
            self.item_list[:] = [ItemWidgetPlain(item) for item in self.lines]
            self.line_count_display.update(len(self.item_list))
        else:
            pattern = ''

            flags = re.UNICODE

            highlight_type = None

            # search string is a regular expression
            if self.regexp_modifier:
                highlight_type = HIGHLIGHT_REGEX
                pattern = search_text
            else:
                if search_text.startswith('"'):
                    # search for whole string between quotation marks
                    highlight_type = HIGHLIGHT_WHOLE_STRING
                    pattern = re.escape(search_text.strip('"'))
                else:
                    # default - split all words and convert to regular expression like: word1.*word2.*word3
                    search_words = search_text.split(' ')
                    if len(search_words) == 1:
                        pattern = re.escape(search_text)
                    else:
                        highlight_type = HIGHLIGHT_WORDS
                        pattern = '.*'.join([re.escape(word) for word in search_words])

            if not self.case_modifier:
                flags |= re.IGNORECASE

            try:
                re_search = re.compile(pattern, flags).search
                items = []
                for item in self.lines:
                    match = re_search(item)
                    if match:
                        if self.show_matches:
                            if highlight_type == HIGHLIGHT_WORDS:
                                items.append(ItemWidgetWords(item, search_words=search_words))
                            else:
                                items.append(ItemWidgetPattern(match))
                        else:
                            items.append(ItemWidgetPlain(item))

                if len(items) > 0:
                    self.item_list[:] = items
                    self.line_count_display.update(relevant_lines=len(self.item_list))
                else:
                    self.item_list[:] = [urwid.Text(('empty_list', 'No selection'))]
                    self.line_count_display.update(relevant_lines=0)

            except re.error as err:
                self.item_list[:] = [urwid.Text(('empty_list', 'Error in regular epression: {}'.format(err)))]
                self.line_count_display.update(relevant_lines=0)

        try:
            self.item_list.set_focus(0)
        except IndexError:  # no items
            pass

    def edit_change(self, widget, search_text):
        self.update_list(search_text)

    def edit_done(self, search_text):
        self.view.set_focus('body')

    def on_unhandled_input(self, input_):
        if isinstance(input_, tuple):  # mouse events
            return True

        if input_ == 'enter':
            try:
                line = self.listbox.get_focus()[0].line
            except AttributeError:  # empty list
                return False

            self.view.set_header(urwid.AttrMap(
                urwid.Text('selected: {}'.format(line)), 'head'))

            self.inject_command(line)
            raise urwid.ExitMainLoop()

        if input_ == 'tab':
            self.toggle_case_modifier()

        elif input_ == 'ctrl r':
            self.toggle_regexp_modifier()

        elif input_ == 'backspace':
            self.search_edit.set_edit_text(self.search_edit.get_text()[0][:-1])
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        elif input_ == 'esc':
            raise urwid.ExitMainLoop()

        # elif input_ == 'delete':
        #     if self.remove_bash_prefix:
        #         try:
        #             line = self.listbox.get_focus()[0].line
        #             self.lines.remove(line)
        #             self.item_list[:] = [ItemWidgetPlain(item) for item in self.lines]

        #             # TODO make this working when in bash mode
        #             call("sed -i '/^{}$/d' ~/.bash_history".format(line), shell=True)
        #         except AttributeError:  # empty list
        #             return True

        elif len(input_) == 1:  # ignore things like tab, enter
            self.search_edit.set_edit_text(self.search_edit.get_text()[0] + input_)
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        return True

    def inject_command(self, command):
        command = (struct.pack('B', c) for c in os.fsencode(command))

        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] = new[3] & ~termios.ECHO  # disable echo
        termios.tcsetattr(fd, termios.TCSANOW, new)
        for c in command:
            fcntl.ioctl(fd, termios.TIOCSTI, c)
        termios.tcsetattr(fd, termios.TCSANOW, old)
