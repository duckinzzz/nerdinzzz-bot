import re

ALLOWED_MD2 = [r'\*\*', r'\*', r'__', r'~~', r'\|\|', r'```', r'`']
MD2_SPECIAL_CHARS = r'[_*\[\]()~`>#+\-=|{}.!]'


def escape_md(text: str) -> str:
    """
    Экранирует спецсимволы MarkdownV2 и исправляет незакрытые inline и блоки кода.
    """

    def escape_char(match):
        s = match.group(0)
        for seq in ALLOWED_MD2:
            if s.startswith(seq):
                return s
        return '\\' + s

    text = re.sub(MD2_SPECIAL_CHARS, escape_char, text)

    if text.count('`') % 2 != 0:
        text += '`'

    if text.count('```') % 2 != 0:
        text += '```'

    return text
