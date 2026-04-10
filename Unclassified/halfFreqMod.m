clear;
myAcq;
%%
Fs = 608e6;  % Sampling frequency
A=data(1,:);
B=data(2,:);
% Reshape to (16, N)
reducedA = reshape(A, 16, []);
reducedB = reshape(B, 16, []);

% Compute pairwise differences (8 x N)
diffA = reducedA(1:8, :) - reducedA(9:16, :);
diffB = reducedB(1:8, :) - reducedB(9:16, :);

% Cross-correlation matrix (8 x 8)
corrMatrix = (diffA * diffB.') / size(diffA, 2);



% Parameters
N = 2^18;
epsilon = 1e-12;

% Compute FFT 
A_fft = abs(fft(A(1:N)));
B_fft = abs(fft(B(1:N)));

% Convert to dB
A_db = 20 * log10(A_fft + epsilon);
B_db = 20 * log10(B_fft + epsilon);

% Frequency axis (MHz)
f = (0:N-1) * (Fs / N) / 1e6;
% === Cross-Correlation Matrix Heatmap + FFT Plot in One Figure ===
figure;

% --- Left: Heatmap ---
subplot(1,2,1);
imagesc(corrMatrix);
colorbar;
title('Cross-Correlation Matrix');
xlabel('B Channels');
ylabel('A Channels');
axis square;
colormap(turbo);

% Annotate values
for i = 1:8
    for j = 1:8
        text(j, i, sprintf('%.2e', corrMatrix(i,j)), ...
            'HorizontalAlignment', 'center', ...
            'Color', 'white', 'FontSize', 10);
    end
end

% --- Right: FFT Overlay ---
subplot(1,2,2);
plot(f, A_db, 'b-', 'DisplayName', 'Channel A'); hold on;
plot(f, B_db, 'r--', 'DisplayName', 'Channel B');
xlim([0 200]);
xlabel('Frequency (MHz)');
ylabel('Magnitude (dB)');
title(sprintf('FFT of Dark Noise'));
legend('show');
grid on;

