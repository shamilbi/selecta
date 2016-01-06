#!/usr/bin/env python3
import fcntl
import termios
import sys
import urwid
import subprocess
import signal
import re
import os
import fileinput


"""Installation:
create a symlink:
$ sudo ln -s selecta.py /usr/bin/selecta
Add an entry to your .bashrc:
bind '"\C-[e":"\C-a\C-kselecta <(history)\C-m"'
"""

list_items = []

for line in fileinput.input():
    line = line.split(None, 1)[1]
    if 'selecta <(history)' not in line:
        list_items.append(line.strip())
list_items.reverse()

line_count_total = 0

palette = [
    ('head', '', '', '', '#aaa', '#618'),
    ('body', '', '', '', '#ddd', '#000'),
    ('focus', '', '', '', '#000', '#da0'),
    ('input', '', '', '', '#fff', '#618'),
    ('pattern', '', '', '', '#f91', ''),
    ('pattern_focus', '', '', '', 'bold,#a00', '#da0'),
    ('line','', '', '', '', ''),
    ('line_focus','', '', '', '#000', '#da0'),
]

signal.signal(signal.SIGINT, lambda *_: sys.exit(0))  # die with style


class ItemWidget(urwid.WidgetWrap):
    def __init__(self, content, match=None):
        self.content = content

        if match is not None:
            parts = content.partition(match)
            self.item = urwid.AttrMap(
                urwid.Text(
                    [parts[0],
                    ('pattern', parts[1]),
                    parts[2]
                ]
            ), 'line', {'pattern': 'pattern_focus', None: 'line_focus'})
        else:
            self.item = urwid.AttrMap(urwid.Text(self.content), 'line', 'line_focus')

        urwid.WidgetWrap.__init__(self, self.item)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class SearchEdit(urwid.Edit):
    __metaclass__ = urwid.signals.MetaSignals
    signals = ['done', 'toggle_regexp_modifier', 'toggle_case_modifier']

    def keypress(self, size, key):
        if key == 'enter':
            urwid.emit_signal(self, 'done', self.get_edit_text())
            return
        elif key == 'esc':
            urwid.emit_signal(self, 'done', None)
            return
        elif key == 'tab':
            urwid.emit_signal(self, 'toggle_case_modifier')
            urwid.emit_signal(self, 'change', self, self.get_edit_text())
            return
        elif key == 'ctrl r':
            urwid.emit_signal(self, 'toggle_regexp_modifier')
            urwid.emit_signal(self, 'change', self, self.get_edit_text())
            return
        elif key == 'down':
            urwid.emit_signal(self, 'done', None)
            return

        urwid.Edit.keypress(self, size, key)


class ResultList(urwid.ListBox):
    __metaclass__ = urwid.signals.MetaSignals
    signals = ['resize']

    def __init__(self, *args):
        self.last_size = 0
        urwid.ListBox.__init__(self, *args)

    def render(self, size, focus):
        if size != self.last_size:
            self.last_size = size
            urwid.emit_signal(self, 'resize', size[1])
        return urwid.ListBox.render(self, size, focus)


class LineCountWidget(urwid.Text):
    pass


class Selector(object):
    def __init__(self):
        self.list_item_widgets = []

        self.line_count_display = LineCountWidget('')
        self.search_edit = SearchEdit(edit_text='')

        self.modifier_display = urwid.Text('')

        urwid.connect_signal(self.search_edit, 'done', self.edit_done)
        urwid.connect_signal(self.search_edit, 'toggle_case_modifier', self.toggle_case_modifier)
        urwid.connect_signal(self.search_edit, 'toggle_regexp_modifier', self.toggle_regexp_modifier)
        urwid.connect_signal(self.search_edit, 'change', self.edit_change)

        header = urwid.AttrMap(urwid.Columns([  # TODO do I really need columns?
            (8, self.line_count_display), # TODO pack at runtime?
            urwid.AttrMap(self.search_edit, 'input', 'input'),  # TODO pack at runtime?
            self.modifier_display,
        ]), 'head', 'head')

        self.item_list = urwid.SimpleListWalker(self.list_item_widgets)
        self.listbox = ResultList(self.item_list)

        urwid.connect_signal(self.listbox, 'resize', self.list_resize)

        self.view = urwid.Frame(body=self.listbox, header=header)

        self.regexp_modifier = False
        self.case_modifier = False

        self.loop = urwid.MainLoop(self.view, palette, unhandled_input=self.on_unhandled_input)
        self.loop.screen.set_terminal_properties(colors=256)

        self.update_list('')
        self.loop.run()

    def list_resize(self, height):
        self.line_count_display.set_text('{}/{} '.format(len(self.list_item_widgets), height))

    def meep(self, *args):
        logger.info(args)

    def toggle_case_modifier(self):
        self.case_modifier = not self.case_modifier
        self.update_modifiers()

    def toggle_regexp_modifier(self):
        self.regexp_modifier = not self.regexp_modifier
        self.update_modifiers()

    def update_modifiers(self):
        modifiers = []
        if self.regexp_modifier:
            modifiers.append('regexp')
        if self.case_modifier:
            modifiers.append('case')

        if len(modifiers) > 0:
            self.modifier_display.set_text('[{}]'.format(','.join(modifiers)))
        else:
            self.modifier_display.set_text('')


    def update_list(self, search_text):
        if search_text == '':  # show whole list_items
            self.item_list[:] = [ItemWidget(item.strip()) for item in list_items]

        else:
            pattern = u'{}'.format(search_text)

            flags = re.IGNORECASE | re.UNICODE

            if not self.regexp_modifier:
                pattern = re.escape(pattern)

            if self.case_modifier:
                flags ^= re.IGNORECASE

            items = []
            for item in list_items:
                match = re.search(pattern, item, flags)
                if match:
                    items.append(ItemWidget(item.strip(), match=match.group()))
            self.item_list[:] = items

        try:
            self.item_list.set_focus(0)
        except:
            pass

    def highlight_pattern(self, match):
        print(match)

    def edit_change(self, widget, search_text):
        self.update_list(search_text)

    def edit_done(self, search_text):
        self.view.set_focus('body')

    def on_unhandled_input(self, input_):
        if isinstance(input_, tuple):  # mouse events
            return True

        if input_ == 'enter':
            try:
                focus = self.listbox.get_focus()[0].content
            except AttributeError:  # empty list
                return

            self.view.set_header(urwid.AttrMap(
                urwid.Text(u'selected: {}'.format(focus)), 'head'))

            self.inject_command(str(focus))
            raise urwid.ExitMainLoop()

        elif input_ == 'tab':
            self.toggle_case_modifier()

        elif input_ == 'ctrl r':
            self.toggle_regexp_modifier()

        elif input_ == 'backspace':
            self.search_edit.set_edit_text(self.search_edit.get_text()[0][:-1])
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        elif input_ == 'esc':
            raise urwid.ExitMainLoop()

        elif len(input_) == 1:  # ignore things like tab, enter
            self.search_edit.set_edit_text(self.search_edit.get_text()[0] + input_)
            self.search_edit.set_edit_pos(len(self.search_edit.get_text()[0]))
            self.view.set_focus('header')

        return True

    def inject_command(self, command):
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] = new[3] & ~termios.ECHO  # disable echo
        termios.tcsetattr(fd, termios.TCSANOW, new)
        for c in command:
            fcntl.ioctl(fd, termios.TIOCSTI, c)
        termios.tcsetattr(fd, termios.TCSANOW, old)


if __name__ == '__main__':
    Selector()