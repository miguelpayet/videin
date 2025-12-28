# Video Sampling and Concatenation - Incremental Build Stages

## Overview
This document outlines five incremental stages for building a Python program that samples and concatenates video files (.ts) into a single MP4 output.

**Program Arguments:**
1. Path: Directory containing .ts video files
2. Interval Duration: Duration of each sample (in seconds)
3. Total Duration: Total duration of output video (in seconds)

---

## Stage 1: Foundation & Discovery

**Objective:** Establish basic infrastructure and discover video files.

**Tasks:**
- Parse command-line arguments (path, interval_duration, total_duration)
- Scan the specified path for all .ts files
- Use PyAV to read each file's metadata:
  - File name
  - File creation time
  - Video duration (in seconds)
- Calculate total combined duration of all videos
- Display formatted output showing all discovered files and total duration

**Deliverables:**
- Runnable script with argument parsing
- List of discovered .ts files with metadata
- Total duration calculation

**Test Checklist:**
- Script accepts three arguments without error
- Correct number of .ts files discovered
- Each file's duration is accurately read
- Total duration is sum of all files

---

## Stage 2: Indexing & Timeline

**Objective:** Build an in-memory index and create the interval structure.

**Tasks:**
- Create an in-memory index of all videos:
  - File name
  - Creation time (as absolute timeline start) (by timestamp)
  - Duration
  - End time (creation_time + duration)
- Sort index by creation time
- Calculate number of intervals: `num_intervals = total_duration / interval_duration`
- Create interval structure:
  - Each interval has: interval_id, start_time, end_time
  - start_time = interval_id * interval_duration
  - end_time = start_time + interval_duration
- Display the timeline structure with all intervals, showing start and end time of the interval and number of video files in the interval

**Deliverables:**
- Video index (sorted by creation time)
- Interval mapping (start/end times)
- Visual representation of timeline

**Test Checklist:**
- Index is correctly sorted by creation time
- Number of intervals is correct
- Each interval has correct start and end times
- Intervals cover the entire timeline without gaps
- Last interval does not exceed total_duration

---

## Stage 3: Sampling Strategy

**Objective:** Determine which video segment to sample for each interval.

**Tasks:**
- For each interval:
  - Pick a random start_time within [interval_start, interval_end - interval_duration]
  - Ensure the full sample (interval_duration) fits within the interval window
  - Ensure that each sample fits within one file
- Identify which file contain the sampled segment:
  - Map sample start_time to file using the index
  - Calculate offset within the file
- Create a sampling plan
- Display the list of samples

**Deliverables:**
- Sampling plan listing:
  - Interval number
  - Random sample start time
  - Source file
  - Offset(s) within file
  - Sample duration

**Test Checklist:**
- All samples are within their respective intervals
- All samples are exactly interval_duration in length
- Each sample fits within available video data
- Samples are randomly distributed (not always from same file)
- Sampling plan covers all intervals in order

---

## Stage 4: Segment Extraction

**Objective:** Extract each sampled segment from source files.

**Tasks:**
- Create a temporary directory for extracted segments
- For each sample in the sampling plan:
  - Use FFmpeg to extract the segment as a .ts file
  - Command: `ffmpeg -i input.ts -ss offset -t duration -c copy output.ts`
  - Use the `-c copy` flag for lossless extraction
  - Save with naming scheme: `sample_000.ts`, `sample_001.ts`, etc.
- Verify extraction succeeded (file exists and is readable with PyAV)
- Log extraction progress and any errors

**Deliverables:**
- Extracted .ts files in temp directory
- Extraction log with status for each sample

**Test Checklist:**
- All sample files are created in temp directory
- Number of extracted files matches number of intervals
- Each extracted file is readable with PyAV
- Each extracted file duration matches expected interval_duration (within 1 frame)
- Files are in correct order (sample_000.ts through sample_N.ts)

---

## Stage 5: Concatenation & Output

**Objective:** Concatenate all samples into final MP4 output.

**Tasks:**
- Create FFmpeg concat file (demuxer list):
  - File: `concat.txt`
  - Format:
    ```
    file 'sample_000.ts'
    file 'sample_001.ts'
    ...
    file 'sample_N.ts'
    ```
- Use FFmpeg concat demuxer to merge samples:
  - Command: `ffmpeg -f concat -safe 0 -i concat.txt -c:v libx264 -c:a aac output.mp4`
- Transcode to MP4 with H.264 video codec
- Verify output file exists and is playable
- Cleanup temporary directory and files
- Display final output information:
  - Output file path
  - Final duration
  - File size

**Deliverables:**
- Final MP4 output file
- Cleanup of temporary files

**Test Checklist:**
- Final MP4 file is created
- MP4 file is readable and playable
- Total duration matches expected output duration (within 1-2 frames)
- Temp directory is cleaned up
- Video quality is acceptable (no visible degradation from source)
- Audio is preserved (if present in source files)

---

## Implementation Notes

- **PyAV**: Use for reading file metadata and verifying extracted segments
- **FFmpeg**: Use for all video extraction and concatenation operations
- **Error Handling**: Implement graceful error handling for missing files, invalid durations, etc.
- **Logging**: Add informative logging at each stage for debugging
- **Testing**: Test each stage independently before proceeding to the next

---

## Success Criteria

The complete program is successful when:
1. All five stages execute without errors
2. The final MP4 output contains sampled content from across the entire video timeline
3. The output duration matches the specified total_duration
4. All temporary files are cleaned up
5. The program can be run repeatedly with different arguments
