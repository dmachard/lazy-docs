import os
import torch
from dataclasses import replace
import uvicorn

from kev.serve import app, Checkpoint, default_device, LoadOptions, Server, is_hub_id

if __name__ == "__main__":
    run_model = os.getenv("KEV_MODEL", "jaredpalmer/kev-0.8b")
    fallback = "runs/smoke"
    run = run_model if is_hub_id(run_model) or os.path.exists(f"{run_model}/head.pt") else fallback

    dev = default_device()
    opts = LoadOptions.from_env()
    if dev == "mps" and opts.attn is None:
        opts = replace(opts, attn="sdpa")
    if dev != "cpu" and opts.dtype is None:
        opts = replace(opts, dtype=torch.bfloat16)
    if opts.backend is None:
        opts = replace(opts, backend="auto")

    print(f"Loading Kev model {run} on {dev}...")
    ck = Checkpoint(run)
    tok, model = ck.load(dev, opts)
    app.state.server = Server(ck, tok, model, dev)

    port = int(os.getenv("PORT", "8009"))
    print(f"Serving Kev on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
