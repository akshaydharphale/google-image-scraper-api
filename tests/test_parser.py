from app.scraper.parser import parse_images, parse_images_chunk, parse_suggestions

# Minimal replica of the embedded result JSON on a Google Images page
# (serialized without whitespace, exactly as Google emits it).
_RESULT_JSON = (
    '[0,"docid_ABC123",'
    '["https://encrypted-tbn0.gstatic.com/images?q=tbn:XYZ&s=10",480,638],'
    '["https://example.com/photos/cappuccino.jpg",1125,1500],'
    'null,1,"rgb(200,194,168)",null,0,'
    '{"2000":[null,"www.example.com","143KB"],'
    '"2003":[null,"90j5ITQ7Z","https://example.com/how-to","How To Make Coffee",'
    'null,0,null,null,null,0,null,null,"Example Site"]}]'
)

PAGE_HTML = f"""
<html><body><script>
var data = {{"key1": [1,{_RESULT_JSON}]}};
</script>
<a href="/search?q=coffee+beans&amp;udm=2&amp;hl=en"><div>Beans</div></a>
<a href="/search?q=coffee&amp;udm=2&amp;tbs=isz:l"><div>Large</div></a>
</body></html>
"""

CHUNK_HTML = (
    '<div class="islrtb isv-r" data-docid="9xjEVn" data-oh="720" '
    'data-ou="https://example.org/img.jpg" data-ow="1280" '
    'data-pt="A Title &amp; More" '
    'data-pu="https://encrypted-tbn0.gstatic.com/images?q=tbn:AAA&amp;s=10" '
    'data-ru="https://example.org/page" data-st="Example Org" '
    'data-tbnid="Ix8T3K" data-tw="300"><a href="#"><img></a></div>'
)


def test_parse_images_extracts_full_result():
    images = parse_images(PAGE_HTML)
    assert len(images) == 1
    img = images[0]
    assert img.position == 1
    assert img.title == "How To Make Coffee"
    assert img.source.name == "Example Site"
    assert img.source.link == "https://example.com/how-to"
    assert img.original.link == "https://example.com/photos/cappuccino.jpg"
    assert img.original.width == 1500
    assert img.original.height == 1125
    assert img.thumbnail.startswith("https://encrypted-tbn0.gstatic.com/")


def test_parse_images_dedupes_by_docid():
    images = parse_images(PAGE_HTML + PAGE_HTML)
    assert len(images) == 1


def test_parse_suggestions_skips_same_query_chips():
    suggestions = parse_suggestions(PAGE_HTML, "coffee")
    titles = [s.title for s in suggestions]
    assert "Beans" in titles  # q extends the query
    assert "Large" not in titles  # q identical -> filter chip, not suggestion


def test_parse_images_chunk():
    images = parse_images_chunk(CHUNK_HTML)
    assert len(images) == 1
    img = images[0]
    assert img.title == "A Title & More"
    assert img.source.name == "Example Org"
    assert img.source.link == "https://example.org/page"
    assert img.original.link == "https://example.org/img.jpg"
    assert img.original.width == 1280
    assert img.original.height == 720
