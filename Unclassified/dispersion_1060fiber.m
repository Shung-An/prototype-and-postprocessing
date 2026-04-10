% Given Data
wavelength = [400 450 500 550 600 650 700 750 800 850 900 950 1000 1050 1100 ...
              1150 1200 1250 1300 1350 1400 1450 1500 1550 1600 1650 1700 ...
              1750 1800 1850 1900 1950 2000 2050 2100 2150 2200 2250 2300 2350 2400]; % nm

dispersion = [-1160.659716 -775.9859422 -544.4681742 -395.927735 -295.7811773 ...
              -225.5188628 -174.6010743 -136.6018409 -107.5761702 -84.91947886 ...
              -66.90648036 -52.32777175 -40.27889133 -30.23137296 -21.72188355 ...
              -14.38478966 -7.975842209 -2.331468352 2.674897341 7.234213228 ...
              11.39828972 15.23966138 18.78497358 22.18743707 25.34269091 ...
              28.43059121 31.40598892 34.27258477 37.0370401 39.76374785 ...
              42.52598274 45.26157227 47.93202872 50.61728814 53.31290964 ...
              56.14175791 58.91287458 61.68399125 64.5187607 67.48675692 70.45031225]; % ps/(nm⋅km)

% Interpolating to 1 nm resolution
new_wavelength = 600:1:1600; % New wavelength range with 1 nm resolution
interp_dispersion = interp1(wavelength, dispersion, new_wavelength, 'spline'); % Interpolate dispersion data


% Constants
m = -1; % order of diffraction, Littrow configuration
M = 1; % magnification of 4f system
Goove = 600; % lines/mm
Lambda = 1/Goove * 1e6; % grating spacing, nm
incident_angle = 26.52 / 180 * pi; % rad
dt_flint2 = 1400; % fs, pulse duration from flint system

% Calculate sin(theta) for each wavelength
sin_theta = new_wavelength / (2 * Lambda);
cos_theta = sqrt(1 - sin_theta.^2); 
new_wavelength_meter = new_wavelength*1e-9;
% L_eff range from -0.03 to 0.03
L_eff_values = linspace(0.20, 0.74, 120 ...
    );
% Preallocate storage for pulse duration results
dt_GDD_grating_fiber = zeros(length(L_eff_values), length(new_wavelength));
GDD_grating_values = zeros(length(L_eff_values), length(new_wavelength)); % Store GDD grating

% Calculate GVD and GDD for fiber with interpolated dispersion
GVD_fiber = -new_wavelength.^2 / (2 * pi * 3e8) .* interp_dispersion * 1e6; % fs^2/m
GDD_fiber = GVD_fiber * 50-300000; % fs^2
dt_GDD_only_fiber = sqrt(dt_flint2^2 + (4*log(2).*GDD_fiber/dt_flint2).^2)/1e3; % ps
% Compute the numerical derivative retaining the same size
TOD_fiber = ((new_wavelength_meter.^2/2/pi/3e8).^2    .*gradient(interp_dispersion, new_wavelength)*1e3+new_wavelength_meter.^3/2/pi^2/9e16.*interp_dispersion*1e-6)*50*1e45;% fs^3

% Compute dt_GDD_and_fiber for each L_eff
for i = 1:length(L_eff_values)
    L_eff = L_eff_values(i);
    GDD_grating = -2 * m^2 * new_wavelength.^3 * 1e-9  * L_eff / (2 * pi * 9e16 * Lambda^2) * 1e30.*(1-(-m*new_wavelength./Lambda-sin_theta).^2).^(-1.5); % fs^2
    GDD_grating_and_Fiber = GDD_grating + GDD_fiber; % fs^2
    TOD_grating(i,:) = -GDD_grating .*3.*new_wavelength.*1e-9./.2./pi./3e8.*1e15; %fs^3
    dt_GDD_grating_fiber(i, :) = sqrt(dt_flint2^2 + (4 * log(2) .* GDD_grating_and_Fiber / dt_flint2).^2) / 1e3; % ps
    
    % Store GDD grating for plotting
    GDD_grating_values(i, :) = GDD_grating;
end
%%
% Plot all results in one figure
figure;
% Generate a colormap (gradient from blue to red) for 100 L_eff values
cmap = jet(length(L_eff_values)); 
% Subplot 1: Plot cos(theta) as a function of wavelength
subplot(3, 1, 1);
hold on;
for i = 1:length(L_eff_values) % Plot every 10th L_eff for clarity
    plot(new_wavelength, TOD_grating(i, :), 'Color', cmap(i, :));
end
plot (new_wavelength, TOD_fiber,'b--');
colormap(cmap); % Apply the colormap
cb1 = colorbar; % Show the colorbar to indicate L_eff values
caxis([min(L_eff_values*100) max(L_eff_values*100)]); % Set the colorbar axis limits to match L_eff range
xlabel('Wavelength (nm)');
ylabel('TOD (fs^3)');
xlim([900 1500]);
ylabel(cb1, 'L_{eff} (cm)'); % Label the colorbar with L_eff
title('TOD of grating and fibe vs Wavelength');
grid on;


% Subplot 2: Pulse Duration vs Wavelength for Various L_{eff}
subplot(3, 1, 2);
hold on;
for i = 1:length(L_eff_values) % Plot every 10th L_eff for clarity
    plot(new_wavelength, dt_GDD_grating_fiber(i, :), 'Color', cmap(i, :));
end
plot(new_wavelength, dt_GDD_only_fiber, 'k--', 'LineWidth', 2, 'DisplayName', 'GDD only fiber');
xlabel('Wavelength (nm)');
ylabel('Pulse Duration (ps)');
xlim([900 1500]);
ylim([0 5]);
title('Pulse Duration vs Wavelength for 100 L_{eff} Values');
grid on;
colormap(cmap); % Apply the colormap
cb1 = colorbar; % Show the colorbar to indicate L_eff values
ylabel(cb1, 'L_{eff} (cm)'); % Label the colorbar with L_eff
caxis([min(L_eff_values*100) max(L_eff_values*100)]); % Set the colorbar axis limits to match L_eff range
hold off;

% Subplot 3: GDD_fiber and GDD_grating vs Wavelength
subplot(3, 1, 3);
hold on;
% plot(new_wavelength, GDD_fiber, 'k--', 'LineWidth', 2, 'DisplayName', 'GDD Fiber');
for i = 1:length(L_eff_values) % Plot every 10th L_eff for clarity
    plot(new_wavelength, GDD_grating_values(i, :), 'Color', cmap(i, :));
end
xlabel('Wavelength (nm)');
ylabel('Group Delay Dispersion (fs^2)');
ylim([-1e7 1e7]);
xlim([900 1500]);
title('GDD of grating and fiber vs Wavelength');
plot(new_wavelength, GDD_fiber,'k--');
colormap(cmap); % Apply the colormap
cb2 = colorbar; % Show the colorbar for L_eff values
ylabel(cb2, 'L_{eff} (cm)'); % Label the colorbar with L_eff
caxis([min(L_eff_values*100) max(L_eff_values*100)]); % Set the colorbar axis limits to match L_eff range
grid on;
hold off;
sgtitle('360R Plane Ruled Diffraction Grating 600 lines/mm'); 
