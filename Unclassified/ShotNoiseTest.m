

% Prompt user for current power in mW
current_power = input('Enter the current power in mW: ');
rep_rate = 8.2e7;
pulse_energy = current_power/rep_rate/1000;
planck = 6.62607015e-34;
wavelength = 1550e-9;
light_freq =  physconst('LightSpeed')/wavelength;
photon_energy = light_freq*planck;
qauntum_efficiency = 0.9;
photon_number = pulse_energy / photon_energy * qauntum_efficiency;
shot_noise_fraction = 1/ (photon_number^0.5);
sensitivity_average= 1;
gain = 24500;
signal_current = current_power * sensitivity_average/1000;
voltage_per_port = signal_current *gain;
shot_noise_per_port = voltage_per_port * shot_noise_fraction;
estimated_shot_noise_with_anti_swing = shot_noise_per_port *2;
voltage_limit = 1.9;
required_cmrr = voltage_limit / voltage_per_port;

A = data(1, :)*10;
B = data(2, :)*10;
x = 1:length(A);

% localMinimaA = islocalmin(A);
% % Replace the existing localMinimaB calculation with this:
% localMinimaB = islocalmin(B);
% xpeakB = find(localMinimaB);

% 
% xpeakA = find(localMinimaA);

%%
shotnumA = [];
commonModeA = [];
intA = [];

for i = 1:length(A)/8
    segment = A((i-1)*8+1:i*8);
    shotnumA(i) = sum(segment) / length(segment);
    commonModeA(i) = std(segment);
    intA(i) = sum(segment.^2) / length(segment);
end
if mod(length(shotnumA), 2) == 0  % Check if length is even
    shotnumAntiSwingA = shotnumA(1:2:end) - shotnumA(2:2:end);
else
    shotnumAntiSwingA = shotnumA(1:2:end-1) - shotnumA(2:2:end);
end
stdShotA = std(shotnumAntiSwingA);
stdCommonModeA = std(commonModeA);
mean_commonModeA = mean(commonModeA);
observed_cmrrA = mean_commonModeA/voltage_per_port;
observed_RINA = stdCommonModeA/voltage_per_port;

shotnumB = [];
commonModeB = [];
intB = [];


for i = 1:length(B)/8
    segment = B((i-1)*8+1:i*8);
    shotnumB(i) = sum(segment) / length(segment);
    commonModeB(i) = std(segment);
    intB(i) = sum(segment.^2) / length(segment);
end
%%
if mod(length(shotnumB), 2) == 0  % Check if length is even
    shotnumAntiSwingB = shotnumB(2:2:end) - shotnumB(1:2:end-1);
else
    shotnumAntiSwingB = shotnumB(2:2:end-1) - shotnumB(1:2:end-2);
end

stdShotB = std(shotnumAntiSwingB);
stdCommonModeB = std(commonModeB);
mean_commonModeB = mean(commonModeB);
observed_cmrrB = mean_commonModeB/voltage_per_port;
observed_RINB = stdCommonModeB/voltage_per_port;

figure;

subplot(4, 2, 1);
text(0.1, 0.9, ['Voltage per port: ' num2str(voltage_per_port, '%.2e') ' V'], 'Units', 'normalized');
hold on;
plot(x(1:8), A(1:8), '-');
last_cycle_start = length(A) - 7;
plot(x(1:8), A(last_cycle_start:end), '--r');
title('Periodicity of Variable A (First and Last Cycle)');
xlabel('Sample Index');
ylabel('Amplitude (V)');
legend('First Cycle', 'Last Cycle');

subplot(4, 2, 2);
text(0.1, 0.9, ['Voltage per port: ' num2str(voltage_per_port, '%.2e') ' V'], 'Units', 'normalized');
hold on;
plot(x(1:8), B(1:8), '-');
last_cycle_start = length(B) - 7;
plot(x(1:8), B(last_cycle_start:end), '--r');
title('Periodicity of Variable B (First and Last Cycle)');
xlabel('Sample Index');
ylabel('Amplitude (V)');
legend('First Cycle', 'Last Cycle');

% Row 2: First 100 points (unchanged)
subplot(4, 2, 3);
plot(x(1:100), A(1:100), '-o', 'DisplayName', 'A');
hold on;
% plot(xpeakA(xpeakA <= 100), A(xpeakA(xpeakA <= 100)), 'rv', 'MarkerFaceColor', 'r', 'DisplayName', 'Local Minima A');
title('Variable A (First 100 points)');
legend;

subplot(4, 2, 4);
plot(x(1:100), B(1:100), '-o', 'DisplayName', 'B');
hold on;
% plot(xpeakB(xpeakB <= 100), B(xpeakB(xpeakB <= 100)), 'rv', 'MarkerFaceColor', 'r', 'DisplayName', 'Local Minima B');
title('Variable B (First 100 points)');
legend;

% Row 3: Shot Noise Histograms (updated with attenuator info)
subplot(4, 2, 5);
histogram(shotnumAntiSwingA, 'Normalization', 'pdf');
title('Observed Anti-Swing Signal Voltage per Cycle, A');
xlabel('Amplitude (V)');
ylabel('Probability Density');
text(0.1, 0.9, ['Std: ' num2str(stdShotA, '%.2e') ' V'], 'Units', 'normalized');
text(0.1, 0.8, ['Est. Shot Noise: ' num2str(estimated_shot_noise_with_anti_swing, '%.2e') ' V'], 'Units', 'normalized');

subplot(4, 2, 6);
histogram(shotnumAntiSwingB, 'Normalization', 'pdf');
title('Observed Anti-Swing Signal Voltage per Cycle, B');
xlabel('Amplitude (V)');
ylabel('Probability Density');
text(0.1, 0.9, ['Std: ' num2str(stdShotB, '%.2e') ' V'], 'Units', 'normalized');
text(0.1, 0.8, ['Est. Shot Noise: ' num2str(estimated_shot_noise_with_anti_swing, '%.2e') ' V'], 'Units', 'normalized');

% Row 4: CMRR and RIN (updated with standard deviation and 10x multiplication)
subplot(4, 2, 7);
histogram(commonModeA, 'Normalization', 'pdf');
title('Common Mode Noise per Cycle, A');
xlabel('Amplitude (V)');
ylabel('Probability Density');
text(0.1, 0.9, ['Observed CMRR: ' num2str(observed_cmrrA, '%.2e') ], 'Units', 'normalized');
text(0.1, 0.8, ['Required CMRR: ' num2str(required_cmrr, '%.2e')], 'Units', 'normalized');
text(0.1, 0.7, ['Observed RIN: ' num2str(observed_RINA, '%.2e') ], 'Units', 'normalized');
text(0.1, 0.6, ['Std Dev: ' num2str(stdCommonModeA*10, '%.2e') ' V'], 'Units', 'normalized');

subplot(4, 2, 8);
histogram(commonModeB, 'Normalization', 'pdf');
title('Common Mode Noise per Cycle, B');
xlabel('Amplitude (V)');
ylabel('Probability Density');
text(0.1, 0.9, ['Observed CMRR: ' num2str(observed_cmrrB, '%.2e')], 'Units', 'normalized');
text(0.1, 0.8, ['Required CMRR: ' num2str(required_cmrr, '%.2e')], 'Units', 'normalized');
text(0.1, 0.7, ['Observed RIN: ' num2str(observed_RINB, '%.2e')], 'Units', 'normalized');
text(0.1, 0.6, ['Std Dev: ' num2str(stdCommonModeB*10, '%.2e') ' V'], 'Units', 'normalized');

% Main title (unchanged)
sgtitle(['Fiber laser 82 MHz, 1550 nm. Power on each port is ' num2str(current_power) ' mW (read by monitor. all values have considered the 20 dB attenuator)']);

% Save Figure (unchanged)
if ~exist('shot noise diagnosis', 'dir')
    mkdir('shot noise diagnosis');
end
set(gcf, 'Position', [0 0 1920 1080]);
saveas(gcf, fullfile('shot noise diagnosis', [num2str(current_power) ' mW.png']));