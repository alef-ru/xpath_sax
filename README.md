XPath SAX (xpath_sax)
=========

Small Python module/script which allows querying really large XML files using a subset of XPath.

See main() in xpath_sax.py for usage.

This was written for a university project so it is very likely that any exotic query will fail miserably.

Commands
------
    python xpath_sax.py xml_file query

Example
------
    python xpath_sax.py example.xml tests/*/test[greeting=hello]
