"""Optional Claude-powered features.

Every function here degrades gracefully: with no ``ANTHROPIC_API_KEY`` the app
still exports the HTML artifact, the SVG card and a usable drawing prompt —
they just come from the deterministic renderers instead.
"""
