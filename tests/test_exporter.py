from crawler.exporter import MarkdownExporter


def test_writes_markdown_file(tmp_path):
    exporter = MarkdownExporter(str(tmp_path))
    path = exporter.write("https://example.com/about", "Hello world")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "https://example.com/about" in content
    assert "Hello world" in content


def test_file_starts_with_url_heading(tmp_path):
    exporter = MarkdownExporter(str(tmp_path))
    path = exporter.write("https://example.com/page", "Some text")
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    assert first_line == "# https://example.com/page"


def test_filename_is_deterministic(tmp_path):
    exporter = MarkdownExporter(str(tmp_path))
    p1 = exporter.write("https://example.com/page", "text")
    p2 = exporter.write("https://example.com/page", "text")
    assert p1.name == p2.name


def test_different_urls_get_different_filenames(tmp_path):
    exporter = MarkdownExporter(str(tmp_path))
    p1 = exporter.write("https://example.com/a", "text")
    p2 = exporter.write("https://example.com/b", "text")
    assert p1.name != p2.name


def test_creates_output_dir_if_missing(tmp_path):
    nested = str(tmp_path / "deep" / "nested")
    exporter = MarkdownExporter(nested)
    path = exporter.write("https://example.com/", "content")
    assert path.exists()
