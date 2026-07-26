from io import StringIO

from DisplayCAL.util_io import EncodedWriter


def test_encoded_writer_write_bytes_with_file_encoding_only():
    """Test EncodedWriter.write with bytes data and only file_encoding set.

    Regression test for #944, subprocess output arrives as bytes with no
    data_encoding configured (only file_encoding), and must still be decoded
    before being written to the text-mode file instead of raising
    TypeError: string argument expected, got 'bytes'.
    """
    file_obj = StringIO()
    writer = EncodedWriter(file_obj, None, "utf-8")

    writer.write(b"hello bytes\n")

    assert file_obj.getvalue() == "hello bytes\n"


def test_encoded_writer_write_bytes_with_no_encoding_set():
    """Test EncodedWriter.write with bytes data and no encoding configured at all."""
    file_obj = StringIO()
    writer = EncodedWriter(file_obj)

    writer.write(b"hello bytes\n")

    assert file_obj.getvalue() == "hello bytes\n"


def test_encoded_writer_write_str_with_file_encoding():
    """Test EncodedWriter.write with str data and file_encoding set.

    The str should go through the encode/decode sanitizing round-trip and
    still be written correctly.
    """
    file_obj = StringIO()
    writer = EncodedWriter(file_obj, None, "utf-8")

    writer.write("hello str\n")

    assert file_obj.getvalue() == "hello str\n"


def test_encoded_writer_write_str_with_no_file_encoding():
    """Test EncodedWriter.write with str data and no file_encoding set."""
    file_obj = StringIO()
    writer = EncodedWriter(file_obj)

    writer.write("hello str\n")

    assert file_obj.getvalue() == "hello str\n"


def test_encoded_writer_write_bytes_with_data_encoding():
    """Test EncodedWriter.write with bytes data and data_encoding set."""
    file_obj = StringIO()
    writer = EncodedWriter(file_obj, "utf-8", "utf-8")

    writer.write("hello data encoding\n".encode())

    assert file_obj.getvalue() == "hello data encoding\n"


def test_encoded_writer_write_mixed_sequence():
    """Test EncodedWriter.write handles alternating bytes/str writes.

    Mirrors the real Worker.exec_cmd() usage, where a single EncodedWriter
    instance sees a mix of str log messages and raw bytes subprocess output.
    """
    file_obj = StringIO()
    writer = EncodedWriter(file_obj, None, "utf-8")

    writer.write("start\n")
    writer.write(b"middle bytes\n")
    writer.write("end\n")

    assert file_obj.getvalue() == "start\nmiddle bytes\nend\n"
