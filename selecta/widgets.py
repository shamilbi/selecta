# coding: utf-8

import re
import urwid

# pylint: disable=unused-argument,no-self-use


class ItemWidget(urwid.WidgetWrap):
    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class ItemWidgetPlain(ItemWidget):
    def __init__(self, line):
        self.line = line
        text = urwid.AttrMap(urwid.Text(self.line), 'line', 'line_focus')
        super().__init__(text)


class ItemWidgetPattern(ItemWidget):
    def __init__(self, line, match=None):
        self.line = line

        # highlight the matches
        matches = re.split('({match})'.format(match=re.escape(match)), self.line)
        parts = []
        for part in matches:
            if part == match:
                parts.append(('pattern', part))
            else:
                parts.append(part)

        text = urwid.AttrMap(
            urwid.Text(parts),
            'line',
            {'pattern': 'pattern_focus', None: 'line_focus'}
        )

        super().__init__(text)


class ItemWidgetWords(ItemWidget):
    def __init__(self, line, search_words):
        self.line = line

        subject = line
        parts = []
        for search_word in search_words:
            if search_word:
                split = subject.split(search_word, maxsplit=1)
                subject = split[-1]
                parts += [split[0], ('pattern', search_word)]

        try:
            parts += split[1]
        except IndexError:
            pass

        text = urwid.AttrMap(
            urwid.Text(parts),
            'line',
            {'pattern': 'pattern_focus', None: 'line_focus'}
        )

        super().__init__(text)


class SearchEdit(urwid.Edit):
    __metaclass__ = urwid.signals.MetaSignals
    signals = ['done', 'toggle_regexp_modifier', 'toggle_case_modifier']

    def keypress(self, size, key):
        if key == 'enter':
            urwid.emit_signal(self, 'done', self.get_edit_text())
            return
        if key == 'esc':
            urwid.emit_signal(self, 'done', None)
            return
        if key == 'tab':
            urwid.emit_signal(self, 'toggle_case_modifier')
            urwid.emit_signal(self, 'change', self, self.get_edit_text())
            return
        if key == 'ctrl r':
            urwid.emit_signal(self, 'toggle_regexp_modifier')
            urwid.emit_signal(self, 'change', self, self.get_edit_text())
            return
        if key == 'down':
            urwid.emit_signal(self, 'done', None)
            return

        super().keypress(size, key)


class ResultList(urwid.ListBox):
    __metaclass__ = urwid.signals.MetaSignals
    signals = ['resize']

    def __init__(self, *args):
        self.last_size = None
        super().__init__(*args)

    def render(self, size, focus=False):
        if size != self.last_size:
            self.last_size = size
            urwid.emit_signal(self, 'resize', size)
        return super().render(size, focus)


class LineCountWidget(urwid.Text):
    def __init__(self):
        super().__init__('')
        self.relevant_lines = 0
        self.visible_lines = 0

    def update(self, relevant_lines=None, visible_lines=None):
        if relevant_lines is not None:
            self.relevant_lines = relevant_lines

        if visible_lines is not None:
            self.visible_lines = visible_lines

        self.set_text('{}/{}'.format(self.visible_lines, self.relevant_lines))
