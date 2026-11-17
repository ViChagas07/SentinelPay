import unicodedata

import ftfy


def repair_text(text: str) -> str:
    repaired = ftfy.fix_text(text, normalization="NFC")
    repaired = unicodedata.normalize("NFC", repaired)
    repaired = repaired.replace("\r\n", "\n").replace("\r", "\n")
    repaired = repaired.replace("\u00a0", " ")
    repaired = repaired.replace("\u2014", ",").replace("\u2013", "-")
    return repaired.replace(" ,", ",")
