lambda0 = 1600e-9;  % Center wavelength (m)
tau0 = 200e-15;    % Initial pulse duration (s)
c = 3e8;           % Speed of light (m/s)
GDD = -1e-30*1e5;   % Group Delay Dispersion (s^2)
TOD = 1e-45*1e7;    % Third Order Dispersion (s^3)

omega0 = 2*pi*c/lambda0;
domega = 2*pi*c/(lambda0^2) * 100e-9;  % Bandwidth (adjust as needed)

omega = linspace(omega0-domega/2, omega0+domega/2, 1000);
phi = 0.5*GDD*(omega-omega0).^2 + (1/6)*TOD*(omega-omega0).^3;
E0 = exp(-(omega-omega0).^2 * (tau0^2/4));
E = E0 .* exp(1i*phi);

t = linspace(-5*tau0, 5*tau0, 1000);
Et = ifft(ifftshift(E));

intensity = abs(Et).^2;
[~, idx] = max(intensity);
half_max = max(intensity)/2;
left_idx = find(intensity(1:idx) <= half_max, 1, 'last');
right_idx = idx + find(intensity(idx:end) <= half_max, 1, 'first') - 1;
pulse_duration = t(right_idx) - t(left_idx);

fprintf('Pulse duration (FWHM): %.2f fs\n', pulse_duration*1e15);

figure;
subplot(2,1,1);
plot(t*1e15, abs(Et).^2);
xlabel('Time (fs)');
ylabel('Intensity (a.u.)');
title('Pulse Intensity');

subplot(2,1,2);
plot(omega, abs(E).^2);
xlabel('Frequency (rad/s)');
ylabel('Spectral Intensity (a.u.)');
title('Pulse Spectrum');