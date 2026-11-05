"""Compatibility entrypoint for the coordinating skill; no work on import."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'kit'))
if __name__=='__main__':
    from auto_reels import main
    sys.exit(main())
