we will build a python program for sampling and concatenation of video files. 
it will take three arguments: (1) a path, an interval duration, and a total duration of the output video. 
the total amount of intervals is determined by the total duration / the interval duration.
this program will scan just the given path for video files with ts extension and calculate the total length of all videos.
an interval is a period of time that is covered in video, with a start time and a duration. all intervals have the same duration. the duration of each interval corresponds to the total length of all videos / the amount of intervals.
this program will create an in-memory index of the video files by interval, in order of the file timestamp, which is in the filename in this format: xxx_YYMMDD-HHMMSSx. consider the DD (day) MM (month) (HHMMSS) (hour-minute-second) segments. 
then it will extract a sample for each interval, based on the total amount of intervals. 
each sample will be interval duration in length. each sample should be taken randomly from one interval by picking a random start time within the interval and ensuring the full sample fits within the window. 
then all the samples should be concatenated ordered by their interval time into one video in mp4 format. 
use ffmpeg. 
use pyAV.
we are doing an incremental build. the build stages are written in BUILD_STAGES.md. 
