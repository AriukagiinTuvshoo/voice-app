"""
Unit tests for Stage 3 Mongolian Grammar, Morphology & Voice Commands Engine.
"""

import unittest
from mongolian_grammar import (
    get_vowel_harmony,
    harmonize_suffix,
    attach_separated_suffixes,
    normalize_postpositions,
    apply_mongolian_grammar,
    process_voice_commands,
    build_whisper_initial_prompt,
)


class TestMongolianGrammar(unittest.TestCase):

    def test_vowel_harmony_classification(self):
        # Back vowels
        self.assertEqual(get_vowel_harmony("Улаанбаатар"), "masculine_a")
        self.assertEqual(get_vowel_harmony("номоор"), "masculine_o")
        self.assertEqual(get_vowel_harmony("ах"), "masculine_a")
        self.assertEqual(get_vowel_harmony("сургууль"), "masculine_a")

        # Front vowels
        self.assertEqual(get_vowel_harmony("гэр"), "feminine_e")
        self.assertEqual(get_vowel_harmony("ээж"), "feminine_e")
        self.assertEqual(get_vowel_harmony("хүүхэд"), "feminine_e")
        self.assertEqual(get_vowel_harmony("нүд"), "feminine_e")
        self.assertEqual(get_vowel_harmony("өвөл"), "feminine_o")

        # Only neutral vowels
        self.assertEqual(get_vowel_harmony("бичиг"), "feminine_e")
        self.assertEqual(get_vowel_harmony("жишиг"), "feminine_e")

    def test_harmonize_suffix(self):
        # Masculine stem takes masculine suffix
        self.assertEqual(harmonize_suffix("ном", "ээс"), "оос")
        self.assertEqual(harmonize_suffix("аав", "ээр"), "аар")
        self.assertEqual(harmonize_suffix("ах", "тэй"), "тай")

        # Feminine stem takes feminine suffix
        self.assertEqual(harmonize_suffix("гэр", "аас"), "ээс")
        self.assertEqual(harmonize_suffix("нүд", "аар"), "ээр")
        self.assertEqual(harmonize_suffix("ээж", "тай"), "тэй")

    def test_attach_separated_suffixes(self):
        # Dative-locative
        self.assertEqual(attach_separated_suffixes("Улаанбаатар т"), "Улаанбаатарт")
        self.assertEqual(attach_separated_suffixes("бид Улаанбаатар т амьдардаг"), "бид Улаанбаатарт амьдардаг")
        self.assertEqual(attach_separated_suffixes("хүн д"), "хүнд")
        self.assertEqual(attach_separated_suffixes("ажил д"), "ажилд")

        # Accusative
        self.assertEqual(attach_separated_suffixes("ном ыг"), "номыг")
        self.assertEqual(attach_separated_suffixes("гэр ийг"), "гэрийг")
        self.assertEqual(attach_separated_suffixes("нохой г"), "нохойг")

        # Ablative & Instrumental
        self.assertEqual(attach_separated_suffixes("гэр ээс"), "гэрээс")
        self.assertEqual(attach_separated_suffixes("гар аар"), "гараар")

        # Plural
        self.assertEqual(attach_separated_suffixes("залуу чууд"), "залуучууд")
        self.assertEqual(attach_separated_suffixes("хүүхд үүд"), "хүүхдүүд")

    def test_postposition_preservation_and_separation(self):
        # Protected words must never be attached to stem
        text = "ширээн дээр тавьсан номын тухай ярилцъя"
        self.assertEqual(attach_separated_suffixes(text), text)

        # Accidental merges must be detached
        self.assertEqual(normalize_postpositions("ширээндээр"), "ширээн дээр")
        self.assertEqual(normalize_postpositions("хуулиндагуу"), "хуулин дагуу")
        self.assertEqual(normalize_postpositions("төслийнтухай"), "төслийн тухай")
        self.assertEqual(normalize_postpositions("бидболон"), "бид болон")
        self.assertEqual(normalize_postpositions("юмуу"), "юм уу")
        self.assertEqual(normalize_postpositions("болнуу"), "болно уу")

        # Full pipeline test
        res = apply_mongolian_grammar("бид ширээндээр ном ыг тавьсан юмуу")
        self.assertEqual(res, "бид ширээн дээр номыг тавьсан юм уу")

    def test_voice_commands_punctuation(self):
        # Period, comma, question, exclamation
        text, action = process_voice_commands("сайн байна уу цэг би өнөөдөр хичээлтэй таслал гэхдээ")
        self.assertIsNone(action)
        self.assertEqual(text, "Сайн байна уу. Би өнөөдөр хичээлтэй, гэхдээ")

        text, action = process_voice_commands("чи хаашаа явах гэж байна асуултын тэмдэг")
        self.assertIsNone(action)
        self.assertEqual(text, "Чи хаашаа явах гэж байна?")

        text, action = process_voice_commands("болгоомжтой бай анхаарлын тэмдэг")
        self.assertIsNone(action)
        self.assertEqual(text, "Болгоомжтой бай!")

    def test_voice_commands_newlines_and_brackets(self):
        text, action = process_voice_commands("эхний өгүүлбэр шинэ мөр хоёр дахь өгүүлбэр")
        self.assertIsNone(action)
        self.assertEqual(text, "Эхний өгүүлбэр\nХоёр дахь өгүүлбэр")

        text, action = process_voice_commands("эхний догол шинэ догол мөр хоёр дахь догол")
        self.assertIsNone(action)
        self.assertEqual(text, "Эхний догол\n\nХоёр дахь догол")

        text, action = process_voice_commands("жишээ нь хаалт нээх монгол улс хаалт хаах")
        self.assertIsNone(action)
        self.assertEqual(text, "Жишээ нь (монгол улс)")

    def test_voice_commands_undo(self):
        # Standalone undo command
        text, action = process_voice_commands("сүүлийнхийг арилга")
        self.assertEqual(action, "undo")
        self.assertEqual(text, "")

        text, action = process_voice_commands("Буцаах")
        self.assertEqual(action, "undo")
        self.assertEqual(text, "")

        # Trailing undo within speech
        text, action = process_voice_commands("өнөөдөр бороотой сүүлийнхийг арилга")
        self.assertIsNone(action)
        self.assertEqual(text, "Өнөөдөр")

    def test_period_noun_disambiguation(self):
        # Should not replace legitimate 'цэг' noun with period
        text, _ = process_voice_commands("бид эхлэх цэг дээр цугларна")
        self.assertIn("эхлэх цэг дээр", text)

        text, _ = process_voice_commands("А цэг рүү очино")
        self.assertIn("А цэг рүү", text)

    def test_build_whisper_initial_prompt(self):
        vocab = [
            "Улаанбаатар",
            "Оюутолгой",
            "Тавантолгой",
            "Улаанбаатар",  # duplicate
            "",              # empty
            "a",             # too short (<2)
            "ХААН Банк",
            "ШУТИС",
            "Монголбанк",
            "VoiceApp",
        ]
        prompt = build_whisper_initial_prompt(vocab, max_chars=100)
        self.assertIn("Улаанбаатар", prompt)
        self.assertIn("Оюутолгой", prompt)
        self.assertIn("Тавантолгой", prompt)
        # Check deduplication
        self.assertEqual(prompt.count("Улаанбаатар"), 1)
        # Check max_chars enforcement
        self.assertLessEqual(len(prompt), 100)


if __name__ == "__main__":
    unittest.main()
