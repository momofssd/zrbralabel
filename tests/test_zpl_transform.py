import unittest

from zpl_transform import rearrange_barcode_fields


class RearrangeBarcodeFieldsTests(unittest.TestCase):
    def test_reorders_requested_records_without_changing_payloads(self):
        source = (
            "^XA^FT620,1180^BXN,4,200,40,40^FD\\*>*06*/Q\r\n"
            "680.000\\*/V332834220SBCUP\\*/PRM0904"
            "\\*/1J91337503968319\\*/1T0062842385E2\\*<\\*^FS^XZ"
        )
        expected = (
            "^XA^FT620,1180^BXN,4,200,40,40^FD\\*>*06*/1J91337503968319"
            "\\*/PRM0904\\*/Q\r\n680.000\\*/V332834220SBCUP"
            "\\*/1T0062842385E2\\*<\\*^FS^XZ"
        )

        self.assertEqual(rearrange_barcode_fields(source), expected)

    def test_reorders_every_datamatrix_field(self):
        field = (
            "^BXN,4,200,40,40^FD\\*>*06*/Qq\\*/Vv\\*/Pp"
            "\\*/1Jj\\*/1Tt\\*<\\*^FS"
        )
        result = rearrange_barcode_fields(f"^XA{field}^FO1,1{field}^XZ")

        self.assertEqual(result.count("*/1Jj\\*/Pp\\*/Qq\\*/Vv\\*/1Tt"), 2)

    def test_leaves_non_datamatrix_and_partial_messages_unchanged(self):
        source = "^XA^BCN,100^FDQq\\*/Vv^FS^BXN,4^FD*/Qq\\*/Vv^FS^XZ"

        self.assertEqual(rearrange_barcode_fields(source), source)

    def test_reorders_qr_code_contents(self):
        source = (
            "^XA^FT620,1210^BQN,2,4,Q,6^FD\\*>*06*/Qq\\*/Vv\\*/Pp"
            "\\*/1Jj\\*/1Tt\\*<\\*^FS^XZ"
        )
        expected = (
            "^XA^FT620,1210^BQN,2,4,Q,6^FD\\*>*06*/1Jj\\*/Pp\\*/Qq"
            "\\*/Vv\\*/1Tt\\*<\\*^FS^XZ"
        )

        self.assertEqual(rearrange_barcode_fields(source), expected)

    def test_keeps_unknown_records_in_their_original_position(self):
        source = (
            "^XA^BXN,4^FD*>*06*/Qq\\*/Xunknown\\*/Vv\\*/Pp"
            "\\*/1Jj\\*/1Tt\\*<\\*^FS^XZ"
        )
        expected = (
            "^XA^BXN,4^FD*>*06*/1Jj\\*/Xunknown\\*/Pp\\*/Qq"
            "\\*/Vv\\*/1Tt\\*<\\*^FS^XZ"
        )

        self.assertEqual(rearrange_barcode_fields(source), expected)


if __name__ == "__main__":
    unittest.main()
