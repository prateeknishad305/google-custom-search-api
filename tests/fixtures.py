"""The result page of Google the tests read."""

SERP_HTML = """
<!doctype html>
<html><head><title>rust async - Google Search</title></head>
<body>
<div id="search">
  <div class="MjjYud">
    <div class="g">
      <div class="yuRUbf"><a href="https://rust-lang.github.io/async-book/08_ecosystem/00_chapter.html" jsname="UWckNb"><h3>The Async Ecosystem - Rust Async Book</h3></a></div>
      <div class="VwiC3b"><span>The async book is a chapter about the async ecosystem of Rust.</span></div>
      <cite>rust-lang.github.io &#8250; async-book &#8250; 08_ecosystem &#8250; 00_chapter.html</cite>
    </div>
  </div>
  <div class="MjjYud">
    <div class="g">
      <div class="yuRUbf"><a href="/url?q=https://tokio.rs/tokio/tutorial/async&sa=U&ved=2ahUKEwi"><h3>Tokio tutorial</h3></a></div>
      <div class="VwiC3b">Learn async with Tokio, the asynchronous runtime of Rust.</div>
      <cite>tokio.rs &#8250; tokio &#8250; tutorial &#8250; async</cite>
    </div>
  </div>
  <div class="MjjYud">
    <div class="g">
      <div class="yuRUbf"><a href="/goto?url=CAESiB0encrypted"><h3>Encrypted destination</h3></a></div>
      <div class="VwiC3b">The destination of this hit is encrypted by Google.</div>
      <cite>github.com &#8250; rust-lang &#8250; tokio&#8230;</cite>
    </div>
  </div>
  <div class="MjjYud">
    <div class="g">
      <div class="yuRUbf"><a href="https://docs.rs/tokio/latest/tokio/"><h3>Another host</h3></a></div>
      <div class="VwiC3b">The documentation of Tokio on another host.</div>
      <cite>docs.rs &#8250; tokio</cite>
    </div>
  </div>
</div>
<script>
window.data = [
 ["Tokio tutorial",null,"https://www.google.com/favicon.ico","https://tokio.rs",["Tokio"],"https://tokio.rs/tokio/tutorial/async",null,null,"https://tokio.rs/tokio/tutorial/async"],
 ["Encrypted destination",null,"https://www.google.com/favicon.ico","https://github.com",["GitHub"],"https://github.com/rust-lang/tokio",null,null,"https://github.com/rust-lang/tokio"]
];
</script>
</body></html>
"""

BLOCKED_HTML = """
<!doctype html><html><body><div>Our systems have detected unusual traffic from your computer network.</div></body></html>
"""

EMPTY_HTML = """
<!doctype html><html><body><div id="search"><p>Your search did not match any documents.</p></div></body></html>
"""
