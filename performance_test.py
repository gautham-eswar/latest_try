#!/usr/bin/env python3
"""
Performance Testing Script for Resume Optimization Pipeline
This script tests the resume optimization pipeline with various input sizes
and generates detailed performance metrics.
"""

import argparse
import requests
import json
import time
import os
import datetime
import csv
import matplotlib.pyplot as plt
from tabulate import tabulate
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('performance_test')

# Constants
DEFAULT_SERVER_URL = "http://localhost:8080"
UPLOAD_ENDPOINT = "/api/upload"
OPTIMIZE_ENDPOINT = "/api/optimize"
DOWNLOAD_ENDPOINT = "/api/download"

# Output formats to test
FORMATS = ["json", "pdf", "txt"]

class PerformanceTest:
    """Handles performance testing of the resume optimization pipeline"""
    
    def __init__(self, server_url, test_files, job_descriptions, output_dir):
        """
        Initialize the performance test
        
        Args:
            server_url (str): Base URL of the resume optimization server
            test_files (list): List of resume files to test
            job_descriptions (list): List of job description files to test
            output_dir (str): Directory for output results
        """
        self.server_url = server_url
        self.test_files = test_files
        self.job_descriptions = job_descriptions
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Results storage
        self.results = []
        self.test_matrix = {}
        
        # Test suite metadata
        self.test_start_time = datetime.datetime.now()
        self.test_end_time = None
        
        logger.info(f"Performance test initialized with {len(test_files)} resume files and "
                   f"{len(job_descriptions)} job descriptions")
    
    def _get_file_size(self, file_path):
        """Get file size in KB"""
        return os.path.getsize(file_path) / 1024
    
    def _count_file_lines(self, file_path):
        """Count number of lines in a file"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return len(f.readlines())
            
    def _get_file_stats(self, file_path):
        """Get file statistics"""
        return {
            'size_kb': self._get_file_size(file_path),
            'line_count': self._count_file_lines(file_path),
            'filename': os.path.basename(file_path)
        }
    
    def upload_resume(self, resume_file):
        """
        Upload a resume file to the API
        
        Args:
            resume_file (str): Path to the resume file
            
        Returns:
            dict: Upload results including status and timing
        """
        logger.info(f"Uploading resume: {resume_file}")
        
        stats = self._get_file_stats(resume_file)
        
        # Prepare the file for upload
        files = {'file': open(resume_file, 'rb')}
        
        start_time = time.time()
        try:
            response = requests.post(
                f"{self.server_url}{UPLOAD_ENDPOINT}",
                files=files,
                timeout=60
            )
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                resume_id = result.get('resume_id')
                logger.info(f"Upload successful. Resume ID: {resume_id}, Duration: {duration:.2f}s")
                
                return {
                    'success': True,
                    'resume_id': resume_id,
                    'duration': duration,
                    'response_size': len(response.content),
                    'status_code': response.status_code,
                    'file_stats': stats
                }
            else:
                logger.error(f"Upload failed with status code {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'duration': duration,
                    'status_code': response.status_code,
                    'error': response.text,
                    'file_stats': stats
                }
                
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"Exception during upload: {str(e)}")
            return {
                'success': False,
                'duration': duration,
                'error': str(e),
                'file_stats': stats
            }
        finally:
            files['file'].close()
    
    def optimize_resume(self, resume_id, job_description_file):
        """
        Optimize a resume using a job description
        
        Args:
            resume_id (str): ID of the uploaded resume
            job_description_file (str): Path to the job description file
            
        Returns:
            dict: Optimization results including status and timing
        """
        logger.info(f"Optimizing resume {resume_id} with job description: {job_description_file}")
        
        stats = self._get_file_stats(job_description_file)
        
        try:
            with open(job_description_file, 'r', encoding='utf-8', errors='ignore') as f:
                job_description = f.read()
            
            payload = {
                'resume_id': resume_id,
                'job_description': job_description
            }
            
            start_time = time.time()
            response = requests.post(
                f"{self.server_url}{OPTIMIZE_ENDPOINT}",
                json=payload,
                timeout=120  # Longer timeout for optimization
            )
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                optimized_id = result.get('optimized_id')
                logger.info(f"Optimization successful. Optimized ID: {optimized_id}, Duration: {duration:.2f}s")
                
                return {
                    'success': True,
                    'optimized_id': optimized_id,
                    'duration': duration,
                    'response_size': len(response.content),
                    'status_code': response.status_code,
                    'jd_stats': stats
                }
            else:
                logger.error(f"Optimization failed with status code {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'duration': duration,
                    'status_code': response.status_code,
                    'error': response.text,
                    'jd_stats': stats
                }
                
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"Exception during optimization: {str(e)}")
            return {
                'success': False,
                'duration': duration,
                'error': str(e),
                'jd_stats': stats
            }
    
    def download_resume(self, resume_id, output_format):
        """
        Download the optimized resume in a specific format
        
        Args:
            resume_id (str): ID of the optimized resume
            output_format (str): Format to download (pdf, json, txt)
            
        Returns:
            dict: Download results including status and timing
        """
        logger.info(f"Downloading resume {resume_id} in {output_format} format")
        
        start_time = time.time()
        try:
            response = requests.get(
                f"{self.server_url}{DOWNLOAD_ENDPOINT}/{resume_id}/{output_format}",
                timeout=30
            )
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code == 200:
                # Save the downloaded file
                file_path = self.output_dir / f"{resume_id}.{output_format}"
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"Download successful. Format: {output_format}, Duration: {duration:.2f}s")
                
                return {
                    'success': True,
                    'format': output_format,
                    'duration': duration,
                    'file_size': len(response.content),
                    'status_code': response.status_code,
                    'file_path': str(file_path)
                }
            else:
                logger.error(f"Download failed with status code {response.status_code}: {response.text}")
                return {
                    'success': False,
                    'format': output_format,
                    'duration': duration,
                    'status_code': response.status_code,
                    'error': response.text
                }
                
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            logger.error(f"Exception during download: {str(e)}")
            return {
                'success': False,
                'format': output_format,
                'duration': duration,
                'error': str(e)
            }
    
    def run_test_case(self, resume_file, job_description_file):
        """
        Run a complete test case with upload, optimize, and download
        
        Args:
            resume_file (str): Path to resume file
            job_description_file (str): Path to job description file
            
        Returns:
            dict: Complete test results
        """
        test_case = {
            'resume_file': resume_file,
            'job_description_file': job_description_file,
            'timestamp': datetime.datetime.now().isoformat(),
            'stages': {}
        }
        
        # Stage 1: Upload
        upload_result = self.upload_resume(resume_file)
        test_case['stages']['upload'] = upload_result
        
        if not upload_result['success']:
            logger.error(f"Test case failed at upload stage")
            test_case['success'] = False
            test_case['failure_point'] = 'upload'
            return test_case
        
        resume_id = upload_result['resume_id']
        
        # Stage 2: Optimize
        optimize_result = self.optimize_resume(resume_id, job_description_file)
        test_case['stages']['optimize'] = optimize_result
        
        if not optimize_result['success']:
            logger.error(f"Test case failed at optimize stage")
            test_case['success'] = False
            test_case['failure_point'] = 'optimize'
            return test_case
        
        optimized_id = optimize_result['optimized_id']
        
        # Stage 3: Download in different formats
        download_results = {}
        for format_type in FORMATS:
            download_result = self.download_resume(optimized_id, format_type)
            download_results[format_type] = download_result
            
            if not download_result['success']:
                logger.warning(f"Download failed for format: {format_type}")
        
        test_case['stages']['download'] = download_results
        
        # Calculate total duration
        total_duration = upload_result['duration'] + optimize_result['duration']
        for format_type in FORMATS:
            if download_results[format_type]['success']:
                total_duration += download_results[format_type]['duration']
        
        test_case['total_duration'] = total_duration
        test_case['success'] = True
        
        return test_case
    
    def run_all_tests(self):
        """Run all test combinations of resumes and job descriptions"""
        logger.info("Starting performance test suite")
        
        total_tests = len(self.test_files) * len(self.job_descriptions)
        completed = 0
        
        for resume_file in self.test_files:
            for job_description_file in self.job_descriptions:
                logger.info(f"Running test case {completed+1}/{total_tests}: "
                           f"{os.path.basename(resume_file)} with {os.path.basename(job_description_file)}")
                
                test_result = self.run_test_case(resume_file, job_description_file)
                self.results.append(test_result)
                
                # Update progress
                completed += 1
                logger.info(f"Completed {completed}/{total_tests} test cases")
        
        self.test_end_time = datetime.datetime.now()
        logger.info(f"Performance test suite completed in "
                  f"{(self.test_end_time - self.test_start_time).total_seconds():.2f} seconds")
        
        return self.results
    
    def _calculate_success_rate(self, stage):
        """Calculate success rate for a specific stage"""
        if not self.results:
            return 0
            
        successful = sum(1 for r in self.results if 
                          stage in r['stages'] and 
                          r['stages'][stage].get('success', False))
        return (successful / len(self.results)) * 100
    
    def _calculate_avg_duration(self, stage):
        """Calculate average duration for a specific stage"""
        durations = [r['stages'][stage]['duration'] for r in self.results 
                    if stage in r['stages'] and 
                    r['stages'][stage].get('success', False) and
                    'duration' in r['stages'][stage]]
        
        if not durations:
            return 0
        return sum(durations) / len(durations)
    
    def generate_summary(self):
        """Generate a summary of the performance test results"""
        if not self.results:
            logger.warning("No results to summarize")
            return {}
        
        summary = {
            'test_start_time': self.test_start_time.isoformat(),
            'test_end_time': self.test_end_time.isoformat() if self.test_end_time else None,
            'total_duration': (self.test_end_time - self.test_start_time).total_seconds() if self.test_end_time else 0,
            'total_tests': len(self.results),
            'successful_tests': sum(1 for r in self.results if r.get('success', False)),
            'stages': {
                'upload': {
                    'success_rate': self._calculate_success_rate('upload'),
                    'avg_duration': self._calculate_avg_duration('upload')
                },
                'optimize': {
                    'success_rate': self._calculate_success_rate('optimize'),
                    'avg_duration': self._calculate_avg_duration('optimize')
                },
                'download': {
                    'formats': {}
                }
            }
        }
        
        # Calculate download stats for each format
        for format_type in FORMATS:
            format_success = sum(1 for r in self.results if 
                                'download' in r['stages'] and 
                                format_type in r['stages']['download'] and 
                                r['stages']['download'][format_type].get('success', False))
            
            format_durations = [r['stages']['download'][format_type]['duration'] 
                               for r in self.results if 
                               'download' in r['stages'] and 
                               format_type in r['stages']['download'] and 
                               r['stages']['download'][format_type].get('success', False) and
                               'duration' in r['stages']['download'][format_type]]
            
            avg_duration = sum(format_durations) / len(format_durations) if format_durations else 0
            
            summary['stages']['download']['formats'][format_type] = {
                'success_rate': (format_success / len(self.results)) * 100 if self.results else 0,
                'avg_duration': avg_duration
            }
        
        return summary
    
    def save_results(self):
        """Save test results to files"""
        results_dir = self.output_dir / "results"
        results_dir.mkdir(exist_ok=True, parents=True)
        
        # Save raw results as JSON
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = results_dir / f"performance_results_{timestamp}.json"
        
        with open(json_path, 'w') as f:
            json.dump({
                'metadata': {
                    'start_time': self.test_start_time.isoformat(),
                    'end_time': self.test_end_time.isoformat() if self.test_end_time else None,
                    'total_tests': len(self.results)
                },
                'results': self.results
            }, f, indent=2)
        
        # Save summary as JSON
        summary = self.generate_summary()
        summary_path = results_dir / f"performance_summary_{timestamp}.json"
        
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Save CSV for easy analysis
        csv_path = results_dir / f"performance_data_{timestamp}.csv"
        
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Resume File', 'Resume Size (KB)', 'JD File', 'JD Size (KB)',
                'Upload Duration', 'Optimization Duration', 
                'Download Duration (JSON)', 'Download Duration (PDF)', 'Download Duration (TXT)',
                'Total Duration', 'Success'
            ])
            
            for result in self.results:
                resume_file = os.path.basename(result['resume_file'])
                resume_size = result['stages']['upload']['file_stats']['size_kb'] if 'file_stats' in result['stages']['upload'] else 0
                
                jd_file = os.path.basename(result['job_description_file'])
                jd_size = result['stages']['optimize']['jd_stats']['size_kb'] if 'jd_stats' in result['stages']['optimize'] else 0
                
                upload_duration = result['stages']['upload']['duration'] if result['stages']['upload'].get('success', False) else 0
                optimize_duration = result['stages']['optimize']['duration'] if result['stages']['optimize'].get('success', False) else 0
                
                download_durations = {
                    fmt: result['stages']['download'][fmt]['duration'] 
                    if 'download' in result['stages'] and 
                       fmt in result['stages']['download'] and 
                       result['stages']['download'][fmt].get('success', False) 
                    else 0
                    for fmt in FORMATS
                }
                
                writer.writerow([
                    resume_file, resume_size, jd_file, jd_size,
                    upload_duration, optimize_duration,
                    download_durations.get('json', 0),
                    download_durations.get('pdf', 0),
                    download_durations.get('txt', 0),
                    result.get('total_duration', 0),
                    'Yes' if result.get('success', False) else 'No'
                ])
        
        logger.info(f"Saved results to {results_dir}")
        return {
            'json_path': str(json_path),
            'summary_path': str(summary_path),
            'csv_path': str(csv_path)
        }
    
    def generate_reports(self):
        """Generate performance reports and visualizations"""
        if not self.results:
            logger.warning("No results to generate reports from")
            return
        
        reports_dir = self.output_dir / "reports"
        reports_dir.mkdir(exist_ok=True, parents=True)
        
        summary = self.generate_summary()
        
        # Generate summary report
        report_path = reports_dir / "performance_report.txt"
        with open(report_path, 'w') as f:
            f.write("=== Resume Optimization Performance Report ===\n\n")
            f.write(f"Test Start: {self.test_start_time}\n")
            f.write(f"Test End: {self.test_end_time}\n")
            f.write(f"Total Duration: {summary['total_duration']:.2f} seconds\n")
            f.write(f"Total Tests: {summary['total_tests']}\n")
            f.write(f"Successful Tests: {summary['successful_tests']} ({(summary['successful_tests']/summary['total_tests'])*100:.2f}%)\n\n")
            
            f.write("=== Stage Performance ===\n\n")
            
            # Format performance data as a table
            table_data = []
            table_data.append(["Stage", "Success Rate", "Avg Duration (s)"])
            table_data.append(["Upload", f"{summary['stages']['upload']['success_rate']:.2f}%", f"{summary['stages']['upload']['avg_duration']:.2f}"])
            table_data.append(["Optimize", f"{summary['stages']['optimize']['success_rate']:.2f}%", f"{summary['stages']['optimize']['avg_duration']:.2f}"])
            
            for fmt in FORMATS:
                fmt_data = summary['stages']['download']['formats'][fmt]
                table_data.append([f"Download ({fmt})", f"{fmt_data['success_rate']:.2f}%", f"{fmt_data['avg_duration']:.2f}"])
            
            f.write(tabulate(table_data, headers="firstrow", tablefmt="grid"))
            f.write("\n\n")
            
            # Top 5 longest-running tests
            f.write("=== Top 5 Longest Tests ===\n\n")
            
            sorted_results = sorted(self.results, key=lambda x: x.get('total_duration', 0), reverse=True)[:5]
            
            long_test_data = []
            long_test_data.append(["Resume", "Job Description", "Total Duration (s)"])
            
            for result in sorted_results:
                resume = os.path.basename(result['resume_file'])
                jd = os.path.basename(result['job_description_file'])
                duration = result.get('total_duration', 0)
                long_test_data.append([resume, jd, f"{duration:.2f}"])
            
            f.write(tabulate(long_test_data, headers="firstrow", tablefmt="grid"))
            
        logger.info(f"Performance report generated at {report_path}")
        
        # Generate visualizations if matplotlib is available
        try:
            # Prepare data for plotting
            stages = ['Upload', 'Optimize', 'Download (json)', 'Download (pdf)', 'Download (txt)']
            durations = [
                summary['stages']['upload']['avg_duration'],
                summary['stages']['optimize']['avg_duration'],
                summary['stages']['download']['formats']['json']['avg_duration'],
                summary['stages']['download']['formats']['pdf']['avg_duration'],
                summary['stages']['download']['formats']['txt']['avg_duration']
            ]
            
            success_rates = [
                summary['stages']['upload']['success_rate'],
                summary['stages']['optimize']['success_rate'],
                summary['stages']['download']['formats']['json']['success_rate'],
                summary['stages']['download']['formats']['pdf']['success_rate'],
                summary['stages']['download']['formats']['txt']['success_rate']
            ]
            
            # Duration chart
            plt.figure(figsize=(10, 6))
            plt.bar(stages, durations, color='skyblue')
            plt.title('Average Duration by Processing Stage')
            plt.xlabel('Stage')
            plt.ylabel('Duration (seconds)')
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(reports_dir / "duration_by_stage.png")
            
            # Success rate chart
            plt.figure(figsize=(10, 6))
            plt.bar(stages, success_rates, color='lightgreen')
            plt.title('Success Rate by Processing Stage')
            plt.xlabel('Stage')
            plt.ylabel('Success Rate (%)')
            plt.xticks(rotation=45)
            plt.ylim(0, 100)
            plt.tight_layout()
            plt.savefig(reports_dir / "success_rate_by_stage.png")
            
            logger.info(f"Performance visualizations generated in {reports_dir}")
            
        except ImportError:
            logger.warning("Matplotlib not available. Skipping visualizations.")
        
        return str(report_path)

def find_test_files(directory, extensions):
    """Find test files with specific extensions in a directory"""
    files = []
    for ext in extensions:
        files.extend(list(Path(directory).glob(f"*.{ext}")))
    return [str(f) for f in files]

def main():
    parser = argparse.ArgumentParser(description='Resume Optimization Performance Test')
    parser.add_argument('--server', default=DEFAULT_SERVER_URL, help='Server URL')
    parser.add_argument('--resume-dir', required=True, help='Directory containing resume test files')
    parser.add_argument('--jd-dir', required=True, help='Directory containing job description test files')
    parser.add_argument('--output', default='performance_results', help='Output directory for results')
    args = parser.parse_args()
    
    # Find test files
    resume_files = find_test_files(args.resume_dir, ['pdf', 'docx', 'txt'])
    jd_files = find_test_files(args.jd_dir, ['txt', 'md', 'pdf'])
    
    if not resume_files:
        logger.error(f"No resume files found in {args.resume_dir}")
        return 1
        
    if not jd_files:
        logger.error(f"No job description files found in {args.jd_dir}")
        return 1
    
    logger.info(f"Found {len(resume_files)} resume files and {len(jd_files)} job description files")
    
    # Run performance tests
    test = PerformanceTest(
        server_url=args.server,
        test_files=resume_files,
        job_descriptions=jd_files,
        output_dir=args.output
    )
    
    try:
        test.run_all_tests()
        test.save_results()
        report_path = test.generate_reports()
        
        logger.info(f"Performance testing completed successfully")
        logger.info(f"See detailed report at: {report_path}")
        return 0
    except Exception as e:
        logger.error(f"Performance testing failed: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main()) 