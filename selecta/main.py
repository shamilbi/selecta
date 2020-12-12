# coding: utf-8

import sys
import argparse
from selecta import Selector

# pylint: disable=line-too-long


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--revert-order', action='store_true', default=False, help='revert the order of the lines')
    parser.add_argument('-b', '--remove-bash-prefix', action='store_true', default=False, help='remove the numeric prefix from bash history')
    parser.add_argument('-z', '--remove-zsh-prefix', action='store_true', default=False, help='remove the time prefix from zsh history')
    parser.add_argument('-e', '--regexp', action='store_true', default=False, help='start in regexp mode')
    parser.add_argument('-a', '--case-sensitive', action='store_true', default=True, help='start in case-sensitive mode')
    parser.add_argument('-d', '--remove-duplicates', action='store_true', default=False, help='remove duplicated lines')
    parser.add_argument('-y', '--show-matches', action='store_true', default=False, help='highlight the part of each line which match the substrings or regexp')
    parser.add_argument('--bash', action='store_true', default=False, help='standard for bash history search, same as -b -i -d')
    parser.add_argument('--zsh', action='store_true', default=False, help='standard for zsh history search, same as -b -i -d')
    parser.add_argument('infile', nargs='?', type=argparse.FileType('r'), default=sys.stdin, help='the file which lines you want to select eg. <(history)')

    args = parser.parse_args()

    if args.infile.name == '<stdin>':
        parser.print_help()
        sys.exit('\nYou must provide an infile!')

    if args.bash:
        args.remove_bash_prefix = True
        args.remove_duplicates = True

    if args.zsh:
        args.revert_order = True
        args.remove_zsh_prefix = True
        args.remove_duplicates = True

    Selector(
        revert_order=args.revert_order,
        remove_bash_prefix=args.remove_bash_prefix,
        remove_zsh_prefix=args.remove_zsh_prefix,
        regexp=args.regexp,
        case_sensitive=args.case_sensitive,
        remove_duplicates=args.remove_duplicates,
        show_matches=args.show_matches,  # TODO highlight more than one part
        infile=args.infile,
        # TODO support missing options
    )


if __name__ == '__main__':
    main()
    # version bump
