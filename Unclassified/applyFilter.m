% File paths
file2 = 'C:\Users\Public\Public Repos\Quantum Measurement UI\GageStreamThruGPU\12hourAqqElectronicNoise.bin';
file1 = 'C:\Users\Public\Public Repos\Quantum Measurement UI\GageStreamThruGPU\electronicNoiseAfterCryoPumpOnline.bin';

% Sampling frequency
fs = 2623/64;

% Define stop bands (in Hz)
stop_bands = [2.8 3.2; 5.6 6.3; 7.6 8;8.4 8.6;8.9 9.1;11.9 12.5; 14.8 15.6;17.8 18.3];

% Process both files
for fileIdx = 1:2
    if fileIdx == 1
        data = readCM(file1);
        [~, filename, ~] = fileparts(file1);
    else
        data = readCM(file2);
        [~, filename, ~] = fileparts(file2);
    end
    
    % Normalize data based on ADC factor and attenuator
    data = data / (32768^2) * (0.24^2 * 10^2); 
    
    % Extract the second column (or any channel of interest)
    column_data = data(:, 10);
    
    % Calculate Allan Deviation for original signal using allanvar
    tau_orig = logspace(log10(1/fs), log10(length(column_data)/fs), length(column_data));
    [avar_orig, tau_orig] = allandev(column_data,  fs); 
    
    % Calculate PSD of original signal
    [pxx_orig, f_orig] = pwelch(column_data, [], [], [], fs);
        % Apply bandstop filter to remove specified frequency bands
    filtered_data = column_data; % Start with original data
    % Apply bandstop filter to remove specified frequency bands
    for i = 1:size(stop_bands, 1)
        f_stop = stop_bands(i, :); % Current stop band
        [b, a] = butter(4, f_stop/(fs/2), 'stop'); % Butterworth filter design
        
        % Apply filter to the current filtered data
        filtered_data = filtfilt(b, a, filtered_data); % Zero-phase filtering
    end
    
     % Calculate Allan Deviation for filtered signal using allanvar
    tau_filtered = logspace(log10(1/fs), log10(length(filtered_data)/(2*fs)), length(filtered_data));
    [avar_filtered, tau_filtered] = allandev(filtered_data,  fs); 
    
    % Calculate PSD of filtered signal
    [pxx_filtered, f_filtered] = pwelch(avar_filtered, [], [], [], fs);
    
    % Create figure for Allan Deviation and PSD comparison
    figure('Name', ['Allan Deviation and PSD Comparison - ' filename], 'NumberTitle', 'off', 'Position', [100, 100, 1920, 1080]);
    
    % Original PSD plot using loglog
    subplot(3,2,1);
    plot(f_orig, 10*log10(pxx_orig));
    title('PSD of Original Signal');
    xlabel('Frequency (Hz)');
    ylabel('Power/Frequency (dB/Hz)');
    grid on;
    
    % Filtered PSD plot using loglog
    subplot(3,2,2);
    plot(f_filtered, 10*log10(pxx_filtered));
    title('PSD of Filtered Signal');
    xlabel('Frequency (Hz)');
    ylabel('Power/Frequency (dB/Hz)');
    grid on;

    % Allan Deviation plots using loglog
    subplot(3,1,[3]);
    
    % Plot Allan deviation for original signal
    plot(avar_orig, tau_orig,  'b', 'DisplayName', 'Original');
    
    % Plot Allan deviation for filtered signal
    plot(avar_filtered, tau_filtered,  'r', 'DisplayName', 'Filtered');
    
    title('Allan Deviation Comparison');
    xlabel('Tau (s)');
    ylabel('Allan Deviation');
    
    legend show;

end

function reshapedData = readCM(filename)
   numElementsPerArray = 64;  
   fid = fopen(filename,'rb'); 
   if fid == -1 
       error('Error opening file'); 
   end

   data=fread(fid,'double'); 
   fclose(fid); 

   numElements=length(data); 
   if mod(numElements,numElementsPerArray) ~=0 
       error('The total number of elements is not a multiple of the expected array size.'); 
   end

   numArrays=numElements/numElementsPerArray; 
   reshapedData=reshape(data,numElementsPerArray,numArrays)'; 
end

function [tau, adev] = allandev(omega, Fs)
    % Calculate Allan variance and deviation for multiple channels
    % Inputs:
    %   omega: Input time series data (N x 64 matrix)
    %   Fs: Sampling frequency in Hz
    % Outputs:
    %   tau: Averaging time
    %   adev: Allan deviation (matrix with 64 columns)

    % Set up tau values
    maxTau = floor(size(omega, 1)/2);
    m = logspace(0, floor(log10(maxTau)), 100);
    m = unique(round(m)); % Ensure unique integer values
    
    % Initialize adev matrix
    adev = zeros(length(m), size(omega, 2));
    
    % Calculate Allan variance for each channel
    for channel = 1:size(omega, 2)
        [avar, tau] = allanvar(omega(:, channel), m, Fs);
        adev(:, channel) = sqrt(avar);
    end
end

