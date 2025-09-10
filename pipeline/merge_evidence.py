#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge individual company evidence CSVs into a master dataset
"""

import pandas as pd
from pathlib import Path
import glob

def merge_evidence_csvs(csv_dir: str = "../out/csv", output_file: str = "../out/master_evidence.csv"):
    """Merge all company evidence CSVs into one master file"""
    
    csv_files = glob.glob(f"{csv_dir}/*_evidence.csv")
    
    if not csv_files:
        print("No evidence CSV files found")
        return None
    
    print(f"Found {len(csv_files)} evidence files:")
    for f in csv_files:
        print(f"  - {Path(f).name}")
    
    # Read and concatenate all CSVs
    dfs = []
    for file in csv_files:
        try:
            df = pd.read_csv(file)
            dfs.append(df)
        except Exception as e:
            print(f"Error reading {file}: {e}")
    
    if not dfs:
        print("No valid CSV files to merge")
        return None
    
    # Merge all dataframes
    master_df = pd.concat(dfs, ignore_index=True)
    
    # Save master file
    master_df.to_csv(output_file, index=False)
    
    print(f"\nMaster dataset created: {output_file}")
    print(f"Total evidence rows: {len(master_df)}")
    print(f"Companies: {master_df['Company'].nunique()}")
    print(f"Non-empty evidence quotes: {len(master_df[master_df['EvidenceQuote'].str.strip() != ''])}")
    
    return master_df

if __name__ == "__main__":
    merge_evidence_csvs()
