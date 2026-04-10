% Assume dataset is 2xN with N = 2e9
Fs = 608e6; % Hz
f_center = 76e6; % Hz
decim_factor = 1e5;
Fs_dec = Fs / decim_factor;
Nfft = 2^20; % 1,048,576

% Initialize figure for plotting
figure;
hold on; % Keep the plot for multiple traces

% --- Loop through channels 1 and 2 ---
for channel_idx = 1:2
    % Select channel and move to GPU
    x = gpuArray(dataset(channel_idx,:));
    
    % Time vector (also GPU)
    N = length(x);
    t = gpuArray((0:N-1).')/Fs;
    
    % --- Step 1: Mix down to baseband and clear temporary variables ---
    x_bb = x(:) .* exp(-1j*2*pi*f_center*t);
    clear x;
    clear t;
    
    % --- Step 2: Manually Decimate with Chunking ---
    % Design the anti-aliasing filter (run this on the CPU first)
    f_cutoff = Fs_dec / 2;
    Wn = f_cutoff / (Fs/2);
    b = firpm(80, [0 Wn Wn*1.05 1], [1 1 0 0], [1 100]); % Example FIR filter design
    
    % Initialize variables for chunking
    chunk_size = 2^24; % A manageable chunk size for the GPU
    overlap = length(b) - 1; % Required overlap for filter state continuity
    num_chunks = ceil((N - overlap) / (chunk_size - overlap));
    x_dec_parts = cell(1, num_chunks);
    z_state = gpuArray(zeros(length(b)-1, 1)); % Filter state on GPU
    
    % Process data in chunks
    for i = 1:num_chunks
        % Define chunk indices
        start_idx = (i-1) * (chunk_size - overlap) + 1;
        end_idx = min(start_idx + chunk_size - 1, N);
        
        % Get chunk and apply filter
        chunk = x_bb(start_idx:end_idx);
        [filtered_chunk, z_state] = filter(b, 1, chunk, z_state);
        
        % Downsample the valid part (exclude overlap)
        downsampled_chunk = filtered_chunk(1:decim_factor:end);
        x_dec_parts{i} = downsampled_chunk;
    end
    clear x_bb;
    clear chunk;
    clear filtered_chunk;
    clear z_state;
    
    % --- Step 3: Concatenate chunks and perform FFT ---
    x_dec = cat(1, x_dec_parts{:});
    clear x_dec_parts;
    
    % FFT
    X = fftshift(fft(x_dec, Nfft));
    clear x_dec;
    
    % --- Step 4: Calculate PSD and plot ---
    psd = abs(X).^2 / (Nfft * Fs_dec);
    clear X;
    psd_db = 10*log10(psd + eps);
    clear psd;
    
    % Frequency axis
    freq = (-Nfft/2:Nfft/2-1)*(Fs_dec/Nfft);
    
    % Plot the current channel's PSD
    plot(freq, psd_db, 'DisplayName', ['Channel ' num2str(channel_idx)]);
end

% --- Finalize plot ---
hold off;
xlabel('Frequency (Hz offset from 76 MHz)');
ylabel('PSD (dB V^2/Hz)');
title('Zoom FFT around 76 MHz (GPU)');
legend('show'); % Display the legend with channel labels
grid on;