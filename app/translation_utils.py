"""
What you need to know is what a django .po file
    documentation here: https://docs.djangoproject.com/fr/3.2/topics/i18n/translation/
What I call a translation dict is a python dictionnary which keys are the msgid (strings or tuple of strings, if multi-line) and values are the corresponding msgstr (strings or tuple of strings, if multi-line)

PROCEDURE to prepare a file for translator (who might have zero clue about python or django)


_, to_translate = get_translation_dict_from_po_file("django.po")

prepare_translation_file_from_dict(to_translate, "django_before_deepL_translation.txt")

# from here you can send this file directly for translation, or you can pre-translate it using deepL
# in that case take the content of the file and copy it into deepL with the language you need
# copy the translation into "django_after_deepL_translation.txt"

merge_deepL_translation_for_proofing("django_before_deepL_translation.txt", "django_after_deepL_translation.txt")

# this creates a "deepL_translation_to_be_proofed.txt" file which you can send to the translators for proofing


# paste the content of the proofed translation into "proofed_translation.txt" and run

trans_dict = read_translated_msgtr("proofed_translation.txt")

insert_translations_into_po_file(trans_dict, "django")

# to generate the file "django_translated.po" which you can rename "django.po" and then commit changes if you agree with them :)

the procedure is executed below when this file is executed as main

"""

import os

LANG = "de"

LOCALE_PATH = f"locale/{LANG}/LC_MESSAGES/"


def get_translation_dict_from_po_file(fname, fpath=LOCALE_PATH, hdr_line_num=19):
    """Reads the .po file and collect untranslated msgstr"""

    with open(os.path.join(fpath, fname), "r") as fp:
        lines = fp.readlines()
    msgids = []
    msgstrs = []
    msg_value = []
    long_line_id = False
    long_line_str = False

    for i, l in enumerate(lines[hdr_line_num:]):

        if l[:5] == "msgid":
            # the value of msgid is not one line
            if l[6:8] == '""':
                long_line_id = True
                msg_value.append(l)
            else:
                msgids.append(l)  # .replace("msgid ", " ")

        elif l[:6] == "msgstr":
            # if the value of msgid was several lines, terminates it
            if long_line_id is True:
                msgids.append(tuple(msg_value))
                msg_value = []
                long_line_id = False

            # the value of msgstr is not one line
            if l[7:9] == '""':
                long_line_str = True
                msg_value.append(l)
            else:
                msgstrs.append(l)

        # if the value of msgstr was several lines, terminates it
        elif l[0] == "\n" and long_line_str is True:
            msgstrs.append(tuple(msg_value))
            msg_value = []
            long_line_str = False

        elif long_line_id is True:
            msg_value.append(l)

        elif long_line_str is True:
            msg_value.append(l)

    trans_dict = {}
    to_translate = {}
    for k, v in zip(msgids, msgstrs):
        trans_dict[k] = v
        if v == tuple(['msgstr ""\n']):
            to_translate[k] = v

    return trans_dict, to_translate


def prepare_translation_file_from_dict(trans_dict, fname, fpath=LOCALE_PATH):
    """Write a translation dict into a file"""
    lines = []
    i = 0
    for k, v in trans_dict.items():
        if isinstance(k, tuple):
            lines = lines + list(k)
        else:
            lines.append(k)

        if isinstance(v, tuple):
            # this is useful to match translations after using deepL
            if v == ('msgstr ""\n',):
                lines = lines + list((f'msgstr "{i}"\n',))
            else:
                lines = lines + list(v)
        else:
            lines.append(v)
        lines.append("\n")
        i = i + 1

    if fname == "django.po":
        print("not overwriting django.po file")
    else:
        with open(f"{fpath}/{fname}", "w") as fp:
            lines = fp.writelines(lines)


def read_translated_msgtr(fname, fpath=LOCALE_PATH):
    """Get the translation dict from a file"""
    trans_dict, _ = get_translation_dict_from_po_file(fname, fpath, hdr_line_num=0)
    return trans_dict


def get_deepL_dict(fname, fpath=LOCALE_PATH):
    """Switch keys and values of the translation dict from a file"""
    trans_dict = read_translated_msgtr(fname, fpath=LOCALE_PATH)
    return {v: k for k, v in trans_dict.items()}


def merge_deepL_translation_for_proofing(fname_source, fname_target, fpath=LOCALE_PATH):
    """Take a .po file and the same file which wen through deepL translation and merge them"""
    dict_source = get_deepL_dict(fname_source, fpath)
    dict_target = get_deepL_dict(fname_target, fpath)

    new_dict = {}
    for ks in dict_source.keys():

        kt = dict_target[ks]
        if isinstance(kt, tuple):
            kt = list(kt)
            kt[0] = kt[0].replace("msgid", "msgstr")
            kt = tuple(kt)
        else:
            kt = kt.replace("msgid", "msgstr")
        new_dict[dict_source[ks]] = kt

    prepare_translation_file_from_dict(new_dict, "deepL_translation_to_be_proofed.txt")

    return new_dict


def insert_translations_into_po_file(trans_dict, fname, fpath=LOCALE_PATH):
    """Reads the .po file and insert translated msgstr from the translation dict"""
    with open(f"{fpath}/{fname}.po", "r") as fp:
        lines = fp.readlines()

    msgids = []
    msgstrs = []
    msg_value = []
    long_line_id = False
    long_line_str = False

    hdr_line_num = 19

    lines_to_write = lines[: hdr_line_num + 1]

    for i, l in enumerate(lines[hdr_line_num:]):

        if l[:5] == "msgid":
            # the value of msgid is not one line
            if l[6:8] == '""':
                long_line_id = True
                msg_value.append(l)
            else:
                msgids.append(l)  # .replace("msgid ", " ")
                lines_to_write.append(l)

        elif l[:6] == "msgstr":
            # if the value of msgid was several lines, terminates it
            if long_line_id is True:
                if len(msg_value) == 1 and msg_value[0] == 'msgid ""\n':
                    pass
                    # print(f"valeur de msgid vide a la ligne {i+hdr_line_num}")
                msgids.append(tuple(msg_value))
                lines_to_write = lines_to_write + msg_value
                msg_value = []
                long_line_id = False

            # the value of msgstr is not one line
            if l[7:9] == '""':
                long_line_str = True
                msg_value.append(l)
            else:
                msgid = msgids[-1]
                if msgid in trans_dict:
                    dict_msgid = trans_dict.pop(msgid)
                    msgstrs.append(dict_msgid)
                    lines_to_write = lines_to_write + list(dict_msgid)
                else:
                    msgstrs.append(l)  # .replace("msgstr ", "")
                    lines_to_write.append(l)

        # if the value of msgstr was several lines, terminates it
        elif l[0] == "\n" and long_line_str is True:
            # insert the dict translation here
            if len(msg_value) == 1 and msg_value[0] == 'msgstr ""\n':
                msgid = msgids[-1]
                if msgid in trans_dict:
                    dict_msgid = trans_dict.pop(msgid)
                    msgstrs.append(dict_msgid)
                    lines_to_write = lines_to_write + list(dict_msgid)
                else:
                    msgstrs.append(tuple(msg_value))
                    lines_to_write = lines_to_write + msg_value
            else:
                msgstrs.append(tuple(msg_value))
                lines_to_write = lines_to_write + msg_value

            msg_value = []
            long_line_str = False
            lines_to_write.append("\n")

        elif long_line_id is True:
            msg_value.append(l)

        elif long_line_str is True:
            msg_value.append(l)
        else:
            lines_to_write.append(l)

    # the remaining items are new elements that were not previously in the .po file
    if len(trans_dict) > 0:
        lines_to_write.append("\n")

    for k, v in trans_dict.items():
        if isinstance(k, tuple):
            lines_to_write = lines_to_write + list(k)
            lines_to_write = lines_to_write + list(v)
        else:
            lines_to_write.append(k)
            lines_to_write.append(v)
        lines_to_write.append("\n")

    with open(f"{fpath}/{fname}_translated.po", "w") as fp:
        lines = fp.writelines(lines_to_write)


if __name__ == "__main__":
    _, to_translate = get_translation_dict_from_po_file("django.po")

    prepare_translation_file_from_dict(
        to_translate, "django_before_deepL_translation.txt"
    )

    # from here you can send this file directly for translation, or you can pre-translate it using deepL
    # in that case take the content of the file and copy it into deepL with the language you need
    # copy the translation into "django_after_deepL_translation.txt"

    merge_deepL_translation_for_proofing(
        "django_before_deepL_translation.txt", "django_after_deepL_translation.txt"
    )

    # this creates a "deepL_translation_to_be_proofed.txt" file which you can send to the translators for proofing

    # paste the content of the proofed translation into "proofed_translation.txt" and run

    trans_dict = read_translated_msgtr("proofed_translation.txt")

    new_trans_dict = {}
    for k, v in trans_dict.items():
        if isinstance(k, tuple):
            k[0].replace("msgid:", "msgid")
            v[0].replace("msgstr:", "msgstr")
            new_trans_dict[k] = v
        else:
            new_trans_dict[k.replace("msgid:", "msgid")] = v.replace(
                "msgstr:", "msgstr"
            )

    trans_dict = new_trans_dict

    insert_translations_into_po_file(trans_dict, "django")

    # to generate the file "django_translated.po" which you can rename "django.po" and then commit changes if you agree with them :)
