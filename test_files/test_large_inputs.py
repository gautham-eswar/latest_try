#!/usr/bin/env python3

import argparse
import requests
import json
import time
import os
import sys
from datetime import datetime

# Constants
DEFAULT_SERVER = "http://localhost:8080"
UPLOAD_ENDPOINT = "/api/upload"
OPTIMIZE_ENDPOINT = "/api/optimize"
DOWNLOAD_ENDPOINT = "/api/download"

class PipelineTest:
    def __init__(self, server_url, resume_path, job_path, output_dir):
        self.server_url = server_url
        self.resume_path = resume_path
        self.job_path = job_path
        self.output_dir = output_dir
        self.resume_id = None
        self.metrics = {
            "upload": {"start": 0, "end": 0, "duration": 0, "status": "not started"},
            "optimize": {"start": 0, "end": 0, "duration": 0, "status": "not started"},
            "download": {"start": 0, "end": 0, "duration": 0, "status": "not started"},
            "total": {"start": 0, "end": 0, "duration": 0, "status": "not started"}
        }
        self.results = {}
        
        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def run_all(self):
        """Run the complete pipeline test"""
        print(f"\n{'='*80}")
        print(f"STARTING LARGE INPUT TEST at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        print(f"Resume file: {self.resume_path}")
        print(f"Job description: {self.job_path}")
        print(f"Server URL: {self.server_url}")
        print(f"Output directory: {self.output_dir}")
        print(f"{'-'*80}\n")
        
        self.metrics["total"]["start"] = time.time()
        
        # Run each stage
        success = self.upload_resume()
        if success:
            success = self.optimize_resume()
        if success:
            self.download_formats = ["json", "txt", "pdf"]
            for fmt in self.download_formats:
                self.download_resume(fmt)
        
        self.metrics["total"]["end"] = time.time()
        self.metrics["total"]["duration"] = self.metrics["total"]["end"] - self.metrics["total"]["start"]
        self.metrics["total"]["status"] = "completed"
        
        # Generate report
        self.generate_report()
    
    def upload_resume(self):
        """Upload the resume file to the server"""
        print(f"[1/3] UPLOAD STAGE - Starting upload of {os.path.basename(self.resume_path)}")
        self.metrics["upload"]["start"] = time.time()
        
        try:
            with open(self.resume_path, 'rb') as f:
                file_content = f.read()
            
            # Get file extension
            ext = os.path.splitext(self.resume_path)[1].lstrip('.')
            if ext == "":
                ext = "txt"
            
            files = {
                'file': (f'test_resume.{ext}', file_content)
            }
            
            response = requests.post(
                f"{self.server_url}{UPLOAD_ENDPOINT}",
                files=files
            )
            
            self.metrics["upload"]["end"] = time.time()
            self.metrics["upload"]["duration"] = self.metrics["upload"]["end"] - self.metrics["upload"]["start"]
            
            if response.status_code == 200:
                result = response.json()
                self.resume_id = result.get('resume_id')
                self.metrics["upload"]["status"] = "success"
                print(f"✅ Upload completed in {self.metrics['upload']['duration']:.2f} seconds")
                print(f"   Resume ID: {self.resume_id}")
                # Store extracted data
                self.results["parsed_resume"] = result.get('data', {})
                return True
            else:
                self.metrics["upload"]["status"] = f"failed with status {response.status_code}"
                print(f"❌ Upload failed with status code {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            self.metrics["upload"]["status"] = f"error: {str(e)}"
            print(f"❌ Upload error: {str(e)}")
            return False
    
    def optimize_resume(self):
        """Optimize the resume against the job description"""
        print(f"\n[2/3] OPTIMIZATION STAGE - Starting optimization with job description")
        self.metrics["optimize"]["start"] = time.time()
        
        try:
            # Read job description
            with open(self.job_path, 'r') as f:
                job_description = f.read()
            
            # Call optimize endpoint
            payload = {
                "resume_id": self.resume_id,
                "job_description": job_description
            }
            
            response = requests.post(
                f"{self.server_url}{OPTIMIZE_ENDPOINT}",
                json=payload
            )
            
            self.metrics["optimize"]["end"] = time.time()
            self.metrics["optimize"]["duration"] = self.metrics["optimize"]["end"] - self.metrics["optimize"]["start"]
            
            if response.status_code == 200:
                result = response.json()
                self.metrics["optimize"]["status"] = "success"
                print(f"✅ Optimization completed in {self.metrics['optimize']['duration']:.2f} seconds")
                self.results["optimized_resume"] = result
                
                # Store content analysis data
                if "analysis" in result:
                    analysis = result["analysis"]
                    print(f"   Keyword Match Score: {analysis.get('match_score', 'N/A')}")
                    print(f"   Content Improvement: {analysis.get('improvement_score', 'N/A')}")
                    
                return True
            else:
                self.metrics["optimize"]["status"] = f"failed with status {response.status_code}"
                print(f"❌ Optimization failed with status code {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            self.metrics["optimize"]["status"] = f"error: {str(e)}"
            print(f"❌ Optimization error: {str(e)}")
            return False
    
    def download_resume(self, format_type):
        """Download the optimized resume in the specified format"""
        print(f"\n[3/3] DOWNLOAD STAGE - Retrieving optimized resume in {format_type.upper()} format")
        
        # Track metrics for this specific format
        format_key = f"download_{format_type}"
        self.metrics[format_key] = {"start": 0, "end": 0, "duration": 0, "status": "not started"}
        self.metrics[format_key]["start"] = time.time()
        
        try:
            response = requests.get(
                f"{self.server_url}{DOWNLOAD_ENDPOINT}/{self.resume_id}/{format_type}"
            )
            
            self.metrics[format_key]["end"] = time.time()
            self.metrics[format_key]["duration"] = self.metrics[format_key]["end"] - self.metrics[format_key]["start"]
            
            # Save the output
            output_path = os.path.join(self.output_dir, f"optimized_resume.{format_type}")
            
            if response.status_code == 200:
                self.metrics[format_key]["status"] = "success"
                print(f"✅ Download {format_type} completed in {self.metrics[format_key]['duration']:.2f} seconds")
                
                # Write the response to a file
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"   Saved to: {output_path}")
                
                # If JSON, store the content in results
                if format_type == "json":
                    try:
                        self.results["downloaded_json"] = response.json()
                    except:
                        print("   Note: Could not parse JSON response")
                
                return True
            else:
                self.metrics[format_key]["status"] = f"failed with status {response.status_code}"
                print(f"❌ Download {format_type} failed with status code {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            self.metrics[format_key]["status"] = f"error: {str(e)}"
            print(f"❌ Download {format_type} error: {str(e)}")
            return False
    
    def generate_report(self):
        """Generate a detailed performance report"""
        report_path = os.path.join(self.output_dir, "performance_report.json")
        
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": {
                "resume_file": self.resume_path,
                "job_description_file": self.job_path,
                "server_url": self.server_url
            },
            "metrics": self.metrics,
            "pipeline_results": {
                "resume_id": self.resume_id,
                "upload_success": self.metrics["upload"]["status"] == "success",
                "optimize_success": self.metrics["optimize"]["status"] == "success",
                "download_success": {}
            }
        }
        
        # Add download success statuses
        for fmt in getattr(self, "download_formats", []):
            format_key = f"download_{fmt}"
            if format_key in self.metrics:
                report["pipeline_results"]["download_success"][fmt] = self.metrics[format_key]["status"] == "success"
        
        # Write report to file
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n{'='*80}")
        print(f"TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total duration: {self.metrics['total']['duration']:.2f} seconds")
        print(f"Upload: {'✅ Success' if self.metrics['upload']['status'] == 'success' else '❌ Failed'} ({self.metrics['upload']['duration']:.2f}s)")
        print(f"Optimize: {'✅ Success' if self.metrics['optimize']['status'] == 'success' else '❌ Failed'} ({self.metrics['optimize']['duration']:.2f}s)")
        
        for fmt in getattr(self, "download_formats", []):
            format_key = f"download_{fmt}"
            if format_key in self.metrics:
                status = "✅ Success" if self.metrics[format_key]["status"] == "success" else "❌ Failed"
                print(f"Download {fmt}: {status} ({self.metrics[format_key]['duration']:.2f}s)")
        
        print(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test resume optimization pipeline with large inputs")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Server URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--resume", required=True, help="Path to resume file")
    parser.add_argument("--job", required=True, help="Path to job description file")
    parser.add_argument("--output", default="./output", help="Output directory for results")
    
    args = parser.parse_args()
    
    # Run the pipeline test
    tester = PipelineTest(
        server_url=args.server,
        resume_path=args.resume,
        job_path=args.job,
        output_dir=args.output
    )
    
    tester.run_all() 

import argparse
import requests
import json
import time
import os
import sys
from datetime import datetime

# Constants
DEFAULT_SERVER = "http://localhost:8080"
UPLOAD_ENDPOINT = "/api/upload"
OPTIMIZE_ENDPOINT = "/api/optimize"
DOWNLOAD_ENDPOINT = "/api/download"

class PipelineTest:
    def __init__(self, server_url, resume_path, job_path, output_dir):
        self.server_url = server_url
        self.resume_path = resume_path
        self.job_path = job_path
        self.output_dir = output_dir
        self.resume_id = None
        self.metrics = {
            "upload": {"start": 0, "end": 0, "duration": 0, "status": "not started"},
            "optimize": {"start": 0, "end": 0, "duration": 0, "status": "not started"},
            "download": {"start": 0, "end": 0, "duration": 0, "status": "not started"},
            "total": {"start": 0, "end": 0, "duration": 0, "status": "not started"}
        }
        self.results = {}
        
        # Ensure output directory exists
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def run_all(self):
        """Run the complete pipeline test"""
        print(f"\n{'='*80}")
        print(f"STARTING LARGE INPUT TEST at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        print(f"Resume file: {self.resume_path}")
        print(f"Job description: {self.job_path}")
        print(f"Server URL: {self.server_url}")
        print(f"Output directory: {self.output_dir}")
        print(f"{'-'*80}\n")
        
        self.metrics["total"]["start"] = time.time()
        
        # Run each stage
        success = self.upload_resume()
        if success:
            success = self.optimize_resume()
        if success:
            self.download_formats = ["json", "txt", "pdf"]
            for fmt in self.download_formats:
                self.download_resume(fmt)
        
        self.metrics["total"]["end"] = time.time()
        self.metrics["total"]["duration"] = self.metrics["total"]["end"] - self.metrics["total"]["start"]
        self.metrics["total"]["status"] = "completed"
        
        # Generate report
        self.generate_report()
    
    def upload_resume(self):
        """Upload the resume file to the server"""
        print(f"[1/3] UPLOAD STAGE - Starting upload of {os.path.basename(self.resume_path)}")
        self.metrics["upload"]["start"] = time.time()
        
        try:
            with open(self.resume_path, 'rb') as f:
                file_content = f.read()
            
            # Get file extension
            ext = os.path.splitext(self.resume_path)[1].lstrip('.')
            if ext == "":
                ext = "txt"
            
            files = {
                'file': (f'test_resume.{ext}', file_content)
            }
            
            response = requests.post(
                f"{self.server_url}{UPLOAD_ENDPOINT}",
                files=files
            )
            
            self.metrics["upload"]["end"] = time.time()
            self.metrics["upload"]["duration"] = self.metrics["upload"]["end"] - self.metrics["upload"]["start"]
            
            if response.status_code == 200:
                result = response.json()
                self.resume_id = result.get('resume_id')
                self.metrics["upload"]["status"] = "success"
                print(f"✅ Upload completed in {self.metrics['upload']['duration']:.2f} seconds")
                print(f"   Resume ID: {self.resume_id}")
                # Store extracted data
                self.results["parsed_resume"] = result.get('data', {})
                return True
            else:
                self.metrics["upload"]["status"] = f"failed with status {response.status_code}"
                print(f"❌ Upload failed with status code {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            self.metrics["upload"]["status"] = f"error: {str(e)}"
            print(f"❌ Upload error: {str(e)}")
            return False
    
    def optimize_resume(self):
        """Optimize the resume against the job description"""
        print(f"\n[2/3] OPTIMIZATION STAGE - Starting optimization with job description")
        self.metrics["optimize"]["start"] = time.time()
        
        try:
            # Read job description
            with open(self.job_path, 'r') as f:
                job_description = f.read()
            
            # Call optimize endpoint
            payload = {
                "resume_id": self.resume_id,
                "job_description": job_description
            }
            
            response = requests.post(
                f"{self.server_url}{OPTIMIZE_ENDPOINT}",
                json=payload
            )
            
            self.metrics["optimize"]["end"] = time.time()
            self.metrics["optimize"]["duration"] = self.metrics["optimize"]["end"] - self.metrics["optimize"]["start"]
            
            if response.status_code == 200:
                result = response.json()
                self.metrics["optimize"]["status"] = "success"
                print(f"✅ Optimization completed in {self.metrics['optimize']['duration']:.2f} seconds")
                self.results["optimized_resume"] = result
                
                # Store content analysis data
                if "analysis" in result:
                    analysis = result["analysis"]
                    print(f"   Keyword Match Score: {analysis.get('match_score', 'N/A')}")
                    print(f"   Content Improvement: {analysis.get('improvement_score', 'N/A')}")
                    
                return True
            else:
                self.metrics["optimize"]["status"] = f"failed with status {response.status_code}"
                print(f"❌ Optimization failed with status code {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            self.metrics["optimize"]["status"] = f"error: {str(e)}"
            print(f"❌ Optimization error: {str(e)}")
            return False
    
    def download_resume(self, format_type):
        """Download the optimized resume in the specified format"""
        print(f"\n[3/3] DOWNLOAD STAGE - Retrieving optimized resume in {format_type.upper()} format")
        
        # Track metrics for this specific format
        format_key = f"download_{format_type}"
        self.metrics[format_key] = {"start": 0, "end": 0, "duration": 0, "status": "not started"}
        self.metrics[format_key]["start"] = time.time()
        
        try:
            response = requests.get(
                f"{self.server_url}{DOWNLOAD_ENDPOINT}/{self.resume_id}/{format_type}"
            )
            
            self.metrics[format_key]["end"] = time.time()
            self.metrics[format_key]["duration"] = self.metrics[format_key]["end"] - self.metrics[format_key]["start"]
            
            # Save the output
            output_path = os.path.join(self.output_dir, f"optimized_resume.{format_type}")
            
            if response.status_code == 200:
                self.metrics[format_key]["status"] = "success"
                print(f"✅ Download {format_type} completed in {self.metrics[format_key]['duration']:.2f} seconds")
                
                # Write the response to a file
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                print(f"   Saved to: {output_path}")
                
                # If JSON, store the content in results
                if format_type == "json":
                    try:
                        self.results["downloaded_json"] = response.json()
                    except:
                        print("   Note: Could not parse JSON response")
                
                return True
            else:
                self.metrics[format_key]["status"] = f"failed with status {response.status_code}"
                print(f"❌ Download {format_type} failed with status code {response.status_code}")
                print(f"   Response: {response.text}")
                return False
                
        except Exception as e:
            self.metrics[format_key]["status"] = f"error: {str(e)}"
            print(f"❌ Download {format_type} error: {str(e)}")
            return False
    
    def generate_report(self):
        """Generate a detailed performance report"""
        report_path = os.path.join(self.output_dir, "performance_report.json")
        
        report = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "config": {
                "resume_file": self.resume_path,
                "job_description_file": self.job_path,
                "server_url": self.server_url
            },
            "metrics": self.metrics,
            "pipeline_results": {
                "resume_id": self.resume_id,
                "upload_success": self.metrics["upload"]["status"] == "success",
                "optimize_success": self.metrics["optimize"]["status"] == "success",
                "download_success": {}
            }
        }
        
        # Add download success statuses
        for fmt in getattr(self, "download_formats", []):
            format_key = f"download_{fmt}"
            if format_key in self.metrics:
                report["pipeline_results"]["download_success"][fmt] = self.metrics[format_key]["status"] == "success"
        
        # Write report to file
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n{'='*80}")
        print(f"TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total duration: {self.metrics['total']['duration']:.2f} seconds")
        print(f"Upload: {'✅ Success' if self.metrics['upload']['status'] == 'success' else '❌ Failed'} ({self.metrics['upload']['duration']:.2f}s)")
        print(f"Optimize: {'✅ Success' if self.metrics['optimize']['status'] == 'success' else '❌ Failed'} ({self.metrics['optimize']['duration']:.2f}s)")
        
        for fmt in getattr(self, "download_formats", []):
            format_key = f"download_{fmt}"
            if format_key in self.metrics:
                status = "✅ Success" if self.metrics[format_key]["status"] == "success" else "❌ Failed"
                print(f"Download {fmt}: {status} ({self.metrics[format_key]['duration']:.2f}s)")
        
        print(f"\nDetailed report saved to: {report_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test resume optimization pipeline with large inputs")
    parser.add_argument("--server", default=DEFAULT_SERVER, help=f"Server URL (default: {DEFAULT_SERVER})")
    parser.add_argument("--resume", required=True, help="Path to resume file")
    parser.add_argument("--job", required=True, help="Path to job description file")
    parser.add_argument("--output", default="./output", help="Output directory for results")
    
    args = parser.parse_args()
    
    # Run the pipeline test
    tester = PipelineTest(
        server_url=args.server,
        resume_path=args.resume,
        job_path=args.job,
        output_dir=args.output
    )
    
    tester.run_all() 