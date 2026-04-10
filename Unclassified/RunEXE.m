clear;
% Specify the path to your executable
exePath = 'C:\Program Files (x86)\Gage\CompuScope\CompuScope C SDK\C Samples\Advanced\GageStreamThruGPU-Modified\x64\Debug\GageStreamThruGPU-Simple.exe';

% exePath = 'C:\Program Files (x86)\Gage\CompuScope\CompuScope MATLAB SDK\Main\GageAcquire.m';
% Replace with the actual command to abort
% Use the system function to run the executable
status = system(exePath);

% Check the status to see if the executable ran successfully
if status == 0
    disp('Executable ran successfully.');
else
    disp('Error running the executable.');
end


