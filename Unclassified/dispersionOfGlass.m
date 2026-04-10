function [gdd_fs2_ref_interpolated, tod_fs3_ref_interpolated] = dispersionOfGlass(new_wavelength,doPlot, thickness)
% Default doPlot to 0 if not provided
if nargin < 1
    doPlot = 0;
end
if doPlot ==1
    % Load the data from the CSV file
    data = readtable('C:\Users\sk231\Downloads\sf66.csv');
    wavelength_um = data.wl; % Wavelength in micrometers
    n = data.n; % Refractive index
    resolution = 3000;
    fitting_factor = 6;

    % Convert wavelength to meters and nanometers
    wavelength_m = wavelength_um * 1e-6; % Convert to meters
    wavelength_nm = wavelength_um * 1e+3; % Convert to nanometers

    % Filter data for the range 1000 nm to 2000 nm
    idx = wavelength_nm >= 600 & wavelength_nm <= 1200;
    wavelength_nm_filtered = wavelength_nm(idx);
    n_filtered = n(idx);
    wavelength_m_filtered = wavelength_m(idx);

    % Perform polynomial curve fitting to smooth the refractive index data
    coeffs = polyfit(wavelength_nm_filtered, n_filtered, fitting_factor);
    n_fitted = polyval(coeffs, wavelength_nm_filtered);

    % Calculate Coefficient of Determination (R^2) to evaluate the fit quality
    y = n_filtered;
    y_fit = n_fitted;
    SS_res = sum((y - y_fit).^2);
    SS_tot = sum((y - mean(y)).^2);
    r_squared = 1 - (SS_res / SS_tot);
    if doPlot == 1
        fprintf('Coefficient of Determination (R^2): %.4f\n', r_squared);
    end

    % Interpolate the fitted data for smoother plots
    wavelength_nm_interpolated = linspace(min(wavelength_nm_filtered), max(wavelength_nm_filtered), resolution);
    n_interpolated = interp1(wavelength_nm_filtered, n_filtered, wavelength_nm_interpolated, 'spline');
    wavelength_m_interpolated = wavelength_nm_interpolated * 1e-9;

    % Convert interpolated wavelengths to angular frequency
    c = 299792458; % Speed of light in m/s
    angular_frequency_interpolated = 2 * pi * c ./ (wavelength_nm_interpolated * 1e-9); % Convert nm to meters

    % Calculate wave number k
    k_interpolated = (2 * pi ./ (wavelength_nm_interpolated * 1e-9)) .* n_interpolated; % k in rad/m

    % Calculate the first derivative of k with respect to angular frequency
    dk_domega = diff(k_interpolated) ./ diff(angular_frequency_interpolated);
    dk_domega_padded = [dk_domega  dk_domega(end)]; % Pad to match length

    % Calculate the first derivative of n with respect to angular frequency
    dn_domega = diff(n_interpolated) ./ diff(angular_frequency_interpolated);
    dn_domega_padded = [dn_domega dn_domega(end)]; % Pad to match length

    % Calculate group velocity
    ng = n_interpolated + angular_frequency_interpolated .* dn_domega_padded;
    vg = c ./ ng;

    % Calculate the first derivative of group velocity with respect to angular frequency
    dvg_domega = (diff(vg) ./ diff(angular_frequency_interpolated));
    dvg_domega_padded = [dvg_domega dvg_domega(end)]; % Pad to match length

    % Calculate GVD (Group Velocity Dispersion)
    k2 = -1 ./ vg.^2 .* dvg_domega_padded;

    % Calculate the first derivative of n with respect to wavelength
    dn_dlambda = diff(n_interpolated) ./ diff(wavelength_m_interpolated);
    dn_dlambda_padded  = [dn_dlambda  dn_dlambda(end)]; % Pad to match length

    % Calculate the second derivative of n with respect to wavelength
    d2n_dlambda2 = diff(dn_dlambda_padded) ./ diff(wavelength_m_interpolated);
    d2n_dlambda2_padded  = [dn_dlambda  dn_dlambda(end)]; % Pad to match length

    % Alternative GVD calculation using wavelength derivatives
    % GVD = -wavelength_m_interpolated.^3 .* d2n_dlambda2_padded./(2*pi*3e+8*3e+8);

    % Convert GVD to fs^2/mm (1 s^2 = 1e24 fs^2 and 1 m = 1000 mm)
    GVD_fs2_mm = k2 * (1e30 / 1e3); % fs^2/mm
    GDD_fs2 = GVD_fs2_mm * thickness;

    % Calculate the second derivative of k with respect to angular frequency
    d2k_domega2 = diff(dk_domega_padded) ./ diff(angular_frequency_interpolated);
    d2k_domega2_padded = [d2k_domega2  d2k_domega2(end)]; % Pad to match length

    % Calculate the third derivative of k with respect to angular frequency
    d3k_domega3 = diff(d2k_domega2_padded) ./ diff(angular_frequency_interpolated);
    d3k_domega3_padded = [d3k_domega3  d3k_domega3(end)]; % Pad to match length

    % Calculate TOD (Third-Order Dispersion)
    dk2_domega = diff(k2) ./ diff(angular_frequency_interpolated);
    dk2_domega_padded = [dk2_domega dk2_domega(end)];

    % Convert TOD to fs^3/mm (1 s^3 = 1e36 fs^3 and 1 m = 1000 mm)
    TOD_fs3_mm = dk2_domega_padded * (1e45/ 1e3); % fs^3/mm
    TOD_fs3 = TOD_fs3_mm * thickness;
end
% Load reference GVD data
gvd_ref = readtable('C:\Users\sk231\Downloads\sf66_gvd.csv');
wavelength_nm_gvd_ref = gvd_ref.Var1;
gvd_fs2_mm_ref = gvd_ref.Var2;

% Load reference TOD data
tod_ref = readtable('C:\Users\sk231\Downloads\sf66_tod.csv');
wavelength_nm_tod_ref = tod_ref.Var1;
tod_fs3_mm_ref = tod_ref.Var2;

% Interpolate reference GVD data
gdd_fs2_ref_interpolated = interp1(wavelength_nm_gvd_ref, gvd_fs2_mm_ref, new_wavelength, 'spline')*thickness;

% Interpolate reference TOD data
tod_fs3_ref_interpolated = interp1(wavelength_nm_tod_ref, tod_fs3_mm_ref, new_wavelength, 'spline')*thickness;

if doPlot == 1
    % Calculate differences
    gvd_diff = GVD_fs2_mm - gvd_fs2_mm_ref_interpolated;
    tod_diff = TOD_fs3_mm - tod_fs3_mm_ref_interpolated;

    % Calculate mean absolute error
    mae_gvd = mean(abs(gvd_diff));
    mae_tod = mean(abs(tod_diff));

    fprintf('Mean Absolute Error (GVD): %.2f fs^2/mm\n', mae_gvd);
    fprintf('Mean Absolute Error (TOD): %.2f fs^3/mm\n', mae_tod);

    % Plot GVD comparison
    figure;
    subplot(2,1,1);
    plot(wavelength_nm_interpolated, GVD_fs2_mm, 'b-', ...
        wavelength_nm_interpolated, gvd_fs2_mm_ref_interpolated, 'r--');
    xlabel('Wavelength (nm)');
    ylabel('GVD (fs^2/mm)');
    title('Group Velocity Dispersion (GVD) Comparison');
    legend('Calculated', 'Reference');
    grid on;

    % Plot TOD comparison
    subplot(2,1,2);
    plot(wavelength_nm_interpolated, TOD_fs3_mm, 'b-', ...
        wavelength_nm_interpolated, tod_fs3_mm_ref_interpolated, 'r--');
    xlabel('Wavelength (nm)');
    ylabel('TOD (fs^3/mm)');
    title('Third-Order Dispersion (TOD) Comparison');
    legend('Calculated', 'Reference');
    grid on;

    % Estimate pulse elongation due to GVD
    FWHM_initial = 120; % Initial pulse width in seconds
    pulse_length_mm = 0.1; % Pulse length in mm (100 um)

    % GVD-induced broadening
    elongated_length_GDD = FWHM_initial * sqrt(1 + (4*log(2)*GDD_fs2/(FWHM_initial^2) ).^2);

    % Plot GVD and TOD
    figure;
    subplot(3,1,1);
    plot(wavelength_nm_interpolated(1:end-3), GVD_fs2_mm(1:end-3));
    xlabel('Wavelength (nm)');
    ylabel('GVD (fs^2/mm)');
    title('Group Velocity Dispersion (GVD)');
    grid on;
end
end
