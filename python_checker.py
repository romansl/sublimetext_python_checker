from subprocess import Popen, PIPE

import sublime
import sublime_plugin
import re

lineExpPEP8 = re.compile(r"(.*):(\d+):(\d+):\s+(.*)")
lineExpPyflakes = re.compile(r"(.*):(\d+):\s+(.*)")


def parsePEP8(line):
    match = lineExpPEP8.match(line)
    if match is not None:
        filename, lineno, col, text = match.groups()
        return (filename, lineno, col, text)


def parsePyflakes(line):
    match = lineExpPyflakes.match(line)
    if match is not None:
        filename, lineno, text = match.groups()
        return (filename, lineno, 0, text)

CHECKERS = [
    (['python.exe', 'c:\Python26\Scripts\pep8-script.py', '-r'], parsePEP8),
    (['python.exe', 'c:\Python26\Scripts\pyflakes-script.py'], parsePyflakes)
    ]


global view_messages
view_messages = {}


class PythonCheckerCommand(sublime_plugin.EventListener):
    def on_load(self, view):
        check_and_mark(view)

    def on_post_save(self, view):
        check_and_mark(view)

    def on_selection_modified(self, view):
        global view_messages
        lineno = view.rowcol(view.sel()[0].end())[0]
        if view.id() in view_messages and lineno in view_messages[view.id()]:
            view.set_status('python_checker', view_messages[view.id()][lineno])
        else:
            view.erase_status('python_checker')


def check_and_mark(view):
    if not 'python' in view.settings().get('syntax').lower():
        return

    messages = []

    for checker, regexp in CHECKERS:
        p = Popen(checker + [view.file_name()],
            stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate(None)
        if stdout:
            print stdout
        if stderr:
            print stderr
        messages += parse_messages(stdout, regexp)
        messages += parse_messages(stderr, regexp)

    outlines = [view.full_line(view.text_point(m['lineno'], 0)) \
                for m in messages]
    view.erase_regions('python_checker_outlines')
    view.add_regions('python_checker_outlines',
        outlines,
        'keyword',
        sublime.DRAW_EMPTY | sublime.DRAW_OUTLINED)

    underlines = []
    for m in messages:
        if m['col']:
            a = view.text_point(m['lineno'], m['col'])
            underlines.append(sublime.Region(a, a))

    view.erase_regions('python_checker_underlines')
    view.add_regions('python_checker_underlines',
        underlines,
        'keyword',
        sublime.DRAW_EMPTY_AS_OVERWRITE | sublime.DRAW_OUTLINED)

    line_messages = {}
    for m in (m for m in messages if m['text']):
        if m['lineno'] in line_messages:
            line_messages[m['lineno']] += ';' + m['text']
        else:
            line_messages[m['lineno']] = m['text']

    global view_messages
    view_messages[view.id()] = line_messages


def parse_messages(checker_output, regexp):
    messages = []
    for i, line in enumerate(checker_output.splitlines()):
        match = regexp(line)
        if match:
            filename, lineno, col, text = match
            messages.append({
                'lineno': int(lineno) - 1,
                'col': int(col) - 1,
                'text': text})

    return messages


def invalid_syntax_col(checker_output, line_index):
    '''
    For error messages like this:

    /Users/vorushin/Python/answers/urls.py:14: invalid syntax
    dict_test = {key: value for (key, value) in [('one', 1), ('two': 2)]}
                                                                    ^
    '''
    for line in checker_output.splitlines()[line_index + 1:]:
        if line.startswith(' ') and line.find('^') != -1:
            return line.find('^')
