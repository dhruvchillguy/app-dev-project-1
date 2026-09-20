import argparse, csv, logging, os, pathlib, sys
from sinchai import clock, config, db, message, reports
from sinchai.db import DEFAULT_DB_PATH

log = logging.getLogger(__name__)

def _setup_logging(db_path):
    log_dir = os.path.join(os.path.dirname(db_path), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(os.path.join(log_dir, "sinchai.log"), maxBytes=1_000_000, backupCount=3)
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s: %(message)s")

def cmd_run(args):
    from sinchai import farm
    cfg = config.get_config(args.db)
    if args.headless:
        _setup_logging(args.db)
        n = farm.run_headless(args.db, cfg, args.mode, args.demo, args.speed, args.seed, args.source, args.ticks)
        print(f"Ran {n} ticks.")
    else:
        from sinchai.app import SinchaiApp
        SinchaiApp(db_path=args.db, cfg=cfg, demo=args.demo, speed=args.speed, seed=args.seed, source=args.source, mode=args.mode).run()

def cmd_mcp(args):
    os.environ.setdefault("SINCHAI_DB", args.db)
    from sinchai.mcp_server import main
    main()

def cmd_export(args):
    con = db.open_db(args.db, query_only=True)
    if os.path.exists(args.out) and not args.force:
        sys.exit(f"File {args.out} already exists. Use --force to overwrite.")
    rows = con.execute(f"SELECT * FROM {args.table}").fetchall()
    if not rows:
        sys.exit(f"No rows in {args.table}.")
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows([dict(r) for r in rows])
    print(f"Exported {len(rows)} rows to {args.out}")

def cmd_brief(args):
    con = db.open_db(args.db, query_only=True)
    print(message.farm_brief(con, db.get_zones(con), config.get_config(args.db)))

def cmd_doctor(args):
    v = sys.version_info
    results = [("Python >= 3.11", "PASS" if v >= (3, 11) else "FAIL", f"{v.major}.{v.minor}.{v.micro}")]
    try:
        con = db.open_db(args.db)
        con.execute("SELECT 1 FROM zones LIMIT 1")
        con.close()
        results.append(("Database access", "PASS", args.db))
    except Exception as e:
        results.append(("Database access", "FAIL", str(e)))
    try:
        import httpx
        r = httpx.get("https://api.open-meteo.com/v1/forecast?latitude=15.45&longitude=75.0&current=temperature_2m", timeout=5)
        results.append(("Weather API", "PASS", f"HTTP {r.status_code}"))
    except Exception as e:
        results.append(("Weather API", "FAIL", str(e)))
    try:
        from mcp.server.mcpserver import MCPServer
        results.append(("MCP import", "PASS", "ok"))
    except Exception as e:
        results.append(("MCP import", "FAIL", str(e)))
    try:
        cols = os.get_terminal_size()
        ok = cols.columns >= 100 and cols.lines >= 30
        results.append(("Terminal size", "PASS" if ok else "WARN", f"{cols.columns}x{cols.lines} (recommend 100x30)"))
    except Exception:
        results.append(("Terminal size", "WARN", "could not detect"))
    for label, status, detail in results:
        print(f"{status:4s}  {label}: {detail}")
    sys.exit(1 if any(r[1] == "FAIL" for r in results) else 0)

def cmd_reset_db(args):
    if input(f"This will delete {args.db}. Type 'yes' to confirm: ").strip().lower() != "yes":
        print("Cancelled.")
        return
    p = pathlib.Path(args.db)
    if p.exists():
        p.unlink()
        for s in ("-wal", "-shm"):
            wp = pathlib.Path(str(p) + s)
            if wp.exists():
                wp.unlink()
    print(f"Deleted {args.db}. Run sinchai run to reinitialise.")

def main():
    import logging.handlers
    p = argparse.ArgumentParser(prog="sinchai", description="Smart irrigation system")
    p.add_argument("--db", default=os.environ.get("SINCHAI_DB", DEFAULT_DB_PATH))
    sub = p.add_subparsers(dest="cmd")
    pr = sub.add_parser("run")
    pr.add_argument("--demo", action="store_true")
    pr.add_argument("--speed", type=float, default=1800.0)
    pr.add_argument("--seed", type=int, default=42)
    pr.add_argument("--source", choices=["sim", "serial"], default="sim")
    pr.add_argument("--port", default=None)
    pr.add_argument("--auto", dest="mode", action="store_const", const="auto", default="manual")
    pr.add_argument("--headless", action="store_true")
    pr.add_argument("--ticks", type=int, default=None)
    sub.add_parser("mcp")
    pe = sub.add_parser("export")
    pe.add_argument("--table", choices=["readings", "alerts"], required=True)
    pe.add_argument("--out", required=True)
    pe.add_argument("--force", action="store_true")
    sub.add_parser("brief")
    sub.add_parser("doctor")
    sub.add_parser("reset-db")
    args = p.parse_args()
    if args.cmd is None:
        args.cmd, args.demo, args.speed, args.seed = "run", False, 1800.0, 42
        args.source, args.mode, args.headless, args.ticks, args.port = "sim", "manual", False, None, None
    dispatch = {"run": cmd_run, "mcp": cmd_mcp, "export": cmd_export,
                "brief": cmd_brief, "doctor": cmd_doctor, "reset-db": cmd_reset_db}
    dispatch[args.cmd](args)
