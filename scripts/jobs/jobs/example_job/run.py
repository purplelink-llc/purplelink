"""Example job. Copy this directory to start a new job."""


def run(ctx):
    if ctx.dry_run:
        ctx.log("dry_run", note="skipping model call")
        return
    res = ctx.client.chat([{"role": "user", "content": "Reply with the word ok."}], max_tokens=16)
    ctx.log("reply", text=res.text[:100], endpoint=res.endpoint, fell_back=res.fell_back)
    # A job with writes_queue true would call ctx.queue_new(markdown) here.
