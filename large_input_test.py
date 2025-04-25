#!/usr/bin/env python3
"""
Large Input Test Script for Resume Optimization System

This script tests the performance of the resume optimization pipeline with larger inputs.
It measures upload times, optimization times, and download times for various formats.
Results are saved to JSON and CSV files, and visualizations are generated.
"""

import argparse
import json
import logging
import os
import random
import time
import requests
import statistics
import csv
from datetime import datetime
from pathlib import Path
import sys
import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

# Configuration
SERVER_URL = "http://localhost:8080"
OUTPUT_DIR = "test_results"
RESUME_DIR = "test_files/resumes"
JOB_DESC_DIR = "test_files/job_descriptions"
LOG_FILE = "large_input_test.log"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class LargeInputTest:
    """Test class for running large input tests on the resume optimization pipeline."""
    
    def __init__(self, server_url=SERVER_URL):
        """Initialize the test runner with server URL and prepare output directory."""
        self.server_url = server_url
        self.results = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = os.path.join(OUTPUT_DIR, self.timestamp)
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Test results will be saved to {self.output_dir}")
    
    def run_tests(self, num_tests=10):
        """Run a series of tests with different resume and job description combinations."""
        resumes = self._get_files(RESUME_DIR)
        job_descriptions = self._get_files(JOB_DESC_DIR)
        
        if not resumes:
            logger.error(f"No resume files found in {RESUME_DIR}")
            return
        
        if not job_descriptions:
            logger.error(f"No job description files found in {JOB_DESC_DIR}")
            return
        
        logger.info(f"Found {len(resumes)} resumes and {len(job_descriptions)} job descriptions")
        logger.info(f"Running {num_tests} tests...")
        
        for i in tqdm(range(num_tests), desc="Running tests"):
            # Select random resume and job description
            resume_path = random.choice(resumes)
            job_desc_path = random.choice(job_descriptions)
            
            test_result = {
                "test_id": i+1,
                "timestamp": datetime.now().isoformat(),
                "resume_file": os.path.basename(resume_path),
                "job_desc_file": os.path.basename(job_desc_path),
                "resume_size": os.path.getsize(resume_path),
                "job_desc_size": os.path.getsize(job_desc_path),
                "upload": {},
                "optimize": {},
                "download": {}
            }
            
            # Run the test pipeline
            try:
                # Upload stage
                resume_id = self._upload_resume(resume_path, test_result)
                if not resume_id:
                    logger.error(f"Failed to upload resume {resume_path}")
                    continue
                
                # Optimization stage
                with open(job_desc_path, 'r', encoding='utf-8') as f:
                    job_description = f.read()
                
                optimized_id = self._optimize_resume(resume_id, job_description, test_result)
                if not optimized_id:
                    logger.error(f"Failed to optimize resume {resume_id}")
                    continue
                
                # Download stage - test all formats
                for format_type in ["json", "txt", "pdf"]:
                    self._download_result(optimized_id, format_type, test_result)
                
                self.results.append(test_result)
            except Exception as e:
                logger.error(f"Error in test #{i+1}: {str(e)}")
        
        # Generate summary and save results
        summary = self._generate_summary()
        self._save_results(summary)
        self._generate_report()
        
        return summary
    
    def _get_files(self, directory):
        """Get all files in the specified directory."""
        path = Path(directory)
        if not path.exists():
            return []
        
        return [str(file) for file in path.glob("*") if file.is_file()]
    
    def _upload_resume(self, resume_path, test_result):
        """Upload a resume and measure the upload time."""
        logger.info(f"Uploading resume: {resume_path}")
        start_time = time.time()
        
        try:
            with open(resume_path, "rb") as file:
                files = {"file": (os.path.basename(resume_path), file)}
                response = requests.post(
                    f"{self.server_url}/api/upload",
                    files=files
                )
            
            end_time = time.time()
            duration = end_time - start_time
            
            test_result["upload"]["duration"] = duration
            test_result["upload"]["status_code"] = response.status_code
            
            if response.status_code == 200:
                data = response.json()
                test_result["upload"]["resume_id"] = data.get("resume_id")
                test_result["upload"]["success"] = True
                logger.info(f"Upload successful: {duration:.2f}s")
                return data.get("resume_id")
            else:
                test_result["upload"]["error"] = response.text
                test_result["upload"]["success"] = False
                logger.error(f"Upload failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            test_result["upload"]["error"] = str(e)
            test_result["upload"]["success"] = False
            test_result["upload"]["duration"] = time.time() - start_time
            logger.error(f"Exception during upload: {str(e)}")
            return None
    
    def _optimize_resume(self, resume_id, job_description, test_result):
        """Optimize a resume with a job description and measure the optimization time."""
        logger.info(f"Optimizing resume: {resume_id}")
        start_time = time.time()
        
        try:
            payload = {
                "resume_id": resume_id,
                "job_description": job_description
            }
            
            response = requests.post(
                f"{self.server_url}/api/optimize",
                json=payload
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            test_result["optimize"]["duration"] = duration
            test_result["optimize"]["status_code"] = response.status_code
            
            if response.status_code == 200:
                data = response.json()
                test_result["optimize"]["optimized_id"] = data.get("optimized_resume_id")
                test_result["optimize"]["metrics"] = data.get("metrics", {})
                test_result["optimize"]["success"] = True
                logger.info(f"Optimization successful: {duration:.2f}s")
                return data.get("optimized_resume_id")
            else:
                test_result["optimize"]["error"] = response.text
                test_result["optimize"]["success"] = False
                logger.error(f"Optimization failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            test_result["optimize"]["error"] = str(e)
            test_result["optimize"]["success"] = False
            test_result["optimize"]["duration"] = time.time() - start_time
            logger.error(f"Exception during optimization: {str(e)}")
            return None
    
    def _download_result(self, optimized_id, format_type, test_result):
        """Download the optimized resume in the specified format and measure download time."""
        logger.info(f"Downloading resume {optimized_id} in {format_type} format")
        start_time = time.time()
        
        try:
            response = requests.get(
                f"{self.server_url}/api/download/{optimized_id}/{format_type}"
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if not test_result["download"].get(format_type):
                test_result["download"][format_type] = {}
            
            test_result["download"][format_type]["duration"] = duration
            test_result["download"][format_type]["status_code"] = response.status_code
            
            if response.status_code == 200:
                content_length = len(response.content)
                test_result["download"][format_type]["size"] = content_length
                test_result["download"][format_type]["success"] = True
                logger.info(f"Download successful ({format_type}): {duration:.2f}s, size: {content_length} bytes")
            else:
                test_result["download"][format_type]["error"] = response.text
                test_result["download"][format_type]["success"] = False
                logger.error(f"Download failed ({format_type}): {response.status_code} - {response.text}")
        except Exception as e:
            test_result["download"][format_type]["error"] = str(e)
            test_result["download"][format_type]["success"] = False
            test_result["download"][format_type]["duration"] = time.time() - start_time
            logger.error(f"Exception during download ({format_type}): {str(e)}")
    
    def _generate_summary(self):
        """Generate summary statistics from the test results."""
        if not self.results:
            return {"error": "No test results available"}
        
        # Extract successful tests
        successful_tests = [t for t in self.results if 
                           t.get("upload", {}).get("success") and 
                           t.get("optimize", {}).get("success")]
        
        # Calculate success rates
        total_tests = len(self.results)
        upload_success = sum(1 for t in self.results if t.get("upload", {}).get("success", False))
        optimize_success = sum(1 for t in self.results if t.get("optimize", {}).get("success", False))
        
        # Calculate download success rates by format
        download_success = {
            format_type: sum(1 for t in self.results if t.get("download", {}).get(format_type, {}).get("success", False))
            for format_type in ["json", "txt", "pdf"]
        }
        
        # Calculate average times for successful tests
        upload_times = [t.get("upload", {}).get("duration", 0) for t in successful_tests]
        optimize_times = [t.get("optimize", {}).get("duration", 0) for t in successful_tests]
        
        download_times = {
            format_type: [t.get("download", {}).get(format_type, {}).get("duration", 0) 
                        for t in successful_tests 
                        if t.get("download", {}).get(format_type, {}).get("success", False)]
            for format_type in ["json", "txt", "pdf"]
        }
        
        # Calculate input/output sizes
        resume_sizes = [t.get("resume_size", 0) for t in successful_tests]
        job_desc_sizes = [t.get("job_desc_size", 0) for t in successful_tests]
        
        output_sizes = {
            format_type: [t.get("download", {}).get(format_type, {}).get("size", 0) 
                        for t in successful_tests 
                        if t.get("download", {}).get(format_type, {}).get("success", False)]
            for format_type in ["json", "txt", "pdf"]
        }
        
        # Compile summary
        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "successful_tests": len(successful_tests),
            "success_rates": {
                "upload": upload_success / total_tests if total_tests > 0 else 0,
                "optimize": optimize_success / total_tests if total_tests > 0 else 0,
                "download": {
                    format_type: download_success[format_type] / total_tests if total_tests > 0 else 0
                    for format_type in download_success
                }
            },
            "average_times": {
                "upload": statistics.mean(upload_times) if upload_times else 0,
                "optimize": statistics.mean(optimize_times) if optimize_times else 0,
                "download": {
                    format_type: statistics.mean(download_times[format_type]) if download_times[format_type] else 0
                    for format_type in download_times
                }
            },
            "input_sizes": {
                "resume": {
                    "mean": statistics.mean(resume_sizes) if resume_sizes else 0,
                    "min": min(resume_sizes) if resume_sizes else 0,
                    "max": max(resume_sizes) if resume_sizes else 0
                },
                "job_description": {
                    "mean": statistics.mean(job_desc_sizes) if job_desc_sizes else 0,
                    "min": min(job_desc_sizes) if job_desc_sizes else 0,
                    "max": max(job_desc_sizes) if job_desc_sizes else 0
                }
            },
            "output_sizes": {
                format_type: {
                    "mean": statistics.mean(output_sizes[format_type]) if output_sizes[format_type] else 0,
                    "min": min(output_sizes[format_type]) if output_sizes[format_type] else 0,
                    "max": max(output_sizes[format_type]) if output_sizes[format_type] else 0
                }
                for format_type in output_sizes
            }
        }
        
        return summary
    
    def _save_results(self, summary):
        """Save detailed results and summary to files."""
        # Save detailed results
        detailed_results_path = os.path.join(self.output_dir, "detailed_results.json")
        with open(detailed_results_path, "w") as f:
            json.dump(self.results, f, indent=2)
        logger.info(f"Detailed results saved to {detailed_results_path}")
        
        # Save summary
        summary_path = os.path.join(self.output_dir, "summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Summary saved to {summary_path}")
        
        # Save summary as CSV for easy analysis
        csv_path = os.path.join(self.output_dir, "summary.csv")
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Total Tests", summary["total_tests"]])
            writer.writerow(["Successful Tests", summary["successful_tests"]])
            writer.writerow(["Upload Success Rate", f"{summary['success_rates']['upload']:.2%}"])
            writer.writerow(["Optimize Success Rate", f"{summary['success_rates']['optimize']:.2%}"])
            
            for format_type in summary["success_rates"]["download"]:
                writer.writerow([f"{format_type.upper()} Download Success Rate", 
                               f"{summary['success_rates']['download'][format_type]:.2%}"])
            
            writer.writerow(["Average Upload Time (s)", f"{summary['average_times']['upload']:.3f}"])
            writer.writerow(["Average Optimize Time (s)", f"{summary['average_times']['optimize']:.3f}"])
            
            for format_type in summary["average_times"]["download"]:
                writer.writerow([f"Average {format_type.upper()} Download Time (s)", 
                               f"{summary['average_times']['download'][format_type]:.3f}"])
        
        logger.info(f"CSV summary saved to {csv_path}")
    
    def _generate_report(self):
        """Generate visualizations and reports from the test results."""
        if not self.results:
            logger.error("No results to generate report from")
            return
        
        try:
            # Create a dataframe for easier analysis
            data = []
            for test in self.results:
                if test.get("upload", {}).get("success") and test.get("optimize", {}).get("success"):
                    row = {
                        "test_id": test["test_id"],
                        "resume_size": test["resume_size"],
                        "job_desc_size": test["job_desc_size"],
                        "upload_time": test["upload"]["duration"],
                        "optimize_time": test["optimize"]["duration"],
                    }
                    
                    for format_type in ["json", "txt", "pdf"]:
                        if test.get("download", {}).get(format_type, {}).get("success"):
                            row[f"{format_type}_download_time"] = test["download"][format_type]["duration"]
                            row[f"{format_type}_size"] = test["download"][format_type]["size"]
                    
                    data.append(row)
            
            if not data:
                logger.warning("No successful tests to generate visualizations")
                return
            
            df = pd.DataFrame(data)
            
            # Set up the plots directory
            plots_dir = os.path.join(self.output_dir, "plots")
            os.makedirs(plots_dir, exist_ok=True)
            
            # 1. Box plot of processing times
            plt.figure(figsize=(12, 8))
            processing_times = df[["upload_time", "optimize_time", 
                                "json_download_time", "txt_download_time", "pdf_download_time"]]
            processing_times = processing_times.dropna()
            processing_times.boxplot()
            plt.title("Processing Times by Stage")
            plt.ylabel("Time (seconds)")
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(os.path.join(plots_dir, "processing_times_boxplot.png"))
            plt.close()
            
            # 2. Scatter plot of total processing time vs input size
            plt.figure(figsize=(12, 8))
            df["total_input_size"] = df["resume_size"] + df["job_desc_size"]
            df["total_processing_time"] = df["upload_time"] + df["optimize_time"]
            plt.scatter(df["total_input_size"], df["total_processing_time"])
            plt.title("Total Processing Time vs. Input Size")
            plt.xlabel("Total Input Size (bytes)")
            plt.ylabel("Total Processing Time (seconds)")
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(os.path.join(plots_dir, "processing_time_vs_size.png"))
            plt.close()
            
            # 3. Bar chart of average times by stage
            avg_times = {
                "Upload": df["upload_time"].mean(),
                "Optimize": df["optimize_time"].mean(),
                "JSON Download": df["json_download_time"].mean() if "json_download_time" in df else 0,
                "TXT Download": df["txt_download_time"].mean() if "txt_download_time" in df else 0,
                "PDF Download": df["pdf_download_time"].mean() if "pdf_download_time" in df else 0
            }
            
            plt.figure(figsize=(12, 8))
            plt.bar(avg_times.keys(), avg_times.values())
            plt.title("Average Processing Time by Stage")
            plt.ylabel("Time (seconds)")
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(os.path.join(plots_dir, "average_processing_times.png"))
            plt.close()
            
            logger.info(f"Visualizations saved to {plots_dir}")
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")


def main():
    """Main function to run the test script."""
    parser = argparse.ArgumentParser(description="Test the resume optimization system with large inputs")
    parser.add_argument("--server-url", default=SERVER_URL, help="URL of the API server")
    parser.add_argument("--num-tests", type=int, default=10, help="Number of tests to run")
    args = parser.parse_args()
    
    # Ensure directories exist
    for directory in [OUTPUT_DIR, RESUME_DIR, JOB_DESC_DIR]:
        os.makedirs(directory, exist_ok=True)
    
    # Run tests
    test_runner = LargeInputTest(server_url=args.server_url)
    summary = test_runner.run_tests(num_tests=args.num_tests)
    
    # Print summary
    if isinstance(summary, dict) and not summary.get("error"):
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total tests: {summary['total_tests']}")
        print(f"Successful tests: {summary['successful_tests']} ({summary['successful_tests']/summary['total_tests']*100:.1f}%)")
        print("\nAverage processing times:")
        print(f"  Upload: {summary['average_times']['upload']:.3f}s")
        print(f"  Optimize: {summary['average_times']['optimize']:.3f}s")
        for format_type in summary['average_times']['download']:
            print(f"  {format_type.upper()} Download: {summary['average_times']['download'][format_type]:.3f}s")
        print("\nInput sizes (bytes):")
        print(f"  Resume: {summary['input_sizes']['resume']['mean']:.0f} avg (min: {summary['input_sizes']['resume']['min']}, max: {summary['input_sizes']['resume']['max']})")
        print(f"  Job Description: {summary['input_sizes']['job_description']['mean']:.0f} avg (min: {summary['input_sizes']['job_description']['min']}, max: {summary['input_sizes']['job_description']['max']})")
        print("\nOutput sizes (bytes):")
        for format_type in summary['output_sizes']:
            print(f"  {format_type.upper()}: {summary['output_sizes'][format_type]['mean']:.0f} avg (min: {summary['output_sizes'][format_type]['min']}, max: {summary['output_sizes'][format_type]['max']})")
        print("=" * 80)
    else:
        print("\nTest run failed. Check logs for details.")


if __name__ == "__main__":
    main() 