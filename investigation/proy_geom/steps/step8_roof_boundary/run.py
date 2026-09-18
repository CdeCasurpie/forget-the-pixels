"""Step 8: ordered color segmentation of vertical panorama strips."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'src'))
from height_estimation.experiment import main

if __name__ == '__main__':
    main(8)
