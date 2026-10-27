"""Export records to CSV."""
import csv


def export(records, path):
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(records)
