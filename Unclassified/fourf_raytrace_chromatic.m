function fourf_wave_propagation_gratings()
% Wave (scalar) simulation of a 4f system with two transmissive gratings.
% Layout (mm): G1@0, L1@200 (f=200mm), Fourier~400, L2@600 (f=200mm), G2@800
% Source: polychromatic around 780 nm (770..790 nm), incoherent sum.

%% ---------------- Parameters ----------------
% Wavelengths (band ~20 nm around 780 nm)
lambda_nm = 770:2:790;         % nm
lambda    = lambda_nm*1e-9;    % m
wweights  = ones(size(lambda)); wweights = wweights/sum(wweights);

% Grid (1D along y; extend to 2D by cloning to x if needed)
Ny   = 4096;                   % samples (power of 2 for FFT speed)
Ly   = 8e-3;                   % aperture window [m] (±4 mm)
dy   = Ly/Ny;                  % sampling pitch
y    = ((-Ny/2):(Ny/2-1))*dy;  % coords (m)
ky   = 2*pi*ifftshift( (-Ny/2:(Ny/2-1)) / Ly );  % spatial freq

% Z positions (m)
zG1 = 0.000;   zL1 = 0.200;   zFour = 0.400;   zL2 = 0.600;   zG2 = 0.800;

% Lenses
f1 = 0.200;  f2 = 0.200;

% Gratings: blazed, 1200 gr/mm (period d)
lines_per_mm = 1200;
d = (1/lines_per_mm)*1e-3;      % m
sigma_G1 = +1;                  % orientation (+1/-1)
sigma_G2 = -1;

% Input field (Gaussian beam / stripe)
w0 = 1.0e-3;                    % waist ~1 mm
E0 = exp(-(y/w0).^2);           % coherent across y at source plane (z<0)
z_src = -0.050;                 % start 50 mm before G1

% Numerical padding anti-alias margin (safety propagation step)
% (Angular spectrum handles large steps; just keep Ly big enough.)

%% ---------------- Convenience handles ----------------
lensTF   = @(f,lam) exp( -1i*pi/(lam*f) * (y).^2 );
ASMprop  = @(E,z,lam) ifft(ifftshift( exp(1i*z*sqrt( (2*pi/lam)^2 - ky.^2 )) ...
                                .* fftshift(fft(E)) ));

% Blazed transmission gratings (phase ramps).
% For target order m=-1 near lambda0, blaze makes that order dominant.
lambda0 = 780e-9;
% Phase slope φ'(y) = 2π * m_target / d * (lam/lambda0) * sigma
m_target = -1;
blazePhase = @(lam, sigma) 2*pi*(m_target/d)*(lam/lambda0).*sigma .* y;  % linear in y
t_grating = @(lam, sigma) exp(1i*blazePhase(lam, sigma));                % phase-only DOE

%% ---------------- Planes to capture ----------------
planes = struct('name',{},'z',{},'I',{},'Iacc',{});
planes(1) = struct('name','Source',     'z', z_src, 'I',[], 'Iacc',[]);
planes(2) = struct('name','After G1',   'z', zG1,   'I',[], 'Iacc',[]);
planes(3) = struct('name','Fourier',    'z', zFour, 'I',[], 'Iacc',[]);
planes(4) = struct('name','After L2',   'z', zL2,   'I',[], 'Iacc',[]);
planes(5) = struct('name','After G2',   'z', zG2,   'I',[], 'Iacc',[]);

%% ---------------- Loop over wavelengths (incoherent sum) ----------------
I_acc = zeros(numel(planes), Ny); % accumulators for intensity
for k = 1:numel(lambda)
    lam = lambda(k);
    w   = wweights(k);

    % Start at source plane
    E = E0;

    % Propagate to G1 (zG1)
    E = ASMprop(E, (zG1 - z_src), lam);
    planes(1).I = abs(E).^2;

    % Apply G1 blaze (−1 order near on-axis at 780 nm)
    E = E .* t_grating(lam, sigma_G1);
    planes(2).I = abs(E).^2;

    % Propagate to L1 (zL1) and through lens
    E = ASMprop(E, (zL1 - zG1), lam);
    E = E .* lensTF(f1, lam);

    % Propagate to Fourier plane (zFour)
    E = ASMprop(E, (zFour - zL1), lam);
    planes(3).I = abs(E).^2;

    % Propagate to L2 and through lens
    E = ASMprop(E, (zL2 - zFour), lam);
    E = E .* lensTF(f2, lam);
    planes(4).I = abs(E).^2;

    % Propagate to G2, apply G2 blaze
    E = ASMprop(E, (zG2 - zL2), lam);
    E = E .* t_grating(lam, sigma_G2);
    planes(5).I = abs(E).^2;

    % Incoherent accumulation
    for p = 1:numel(planes)
        I_acc(p,:) = I_acc(p,:) + w * planes(p).I;
    end
end

%% ---------------- Plots ----------------
figure('Color','w','Name','4f Wave Propagation (1D cut)');
for p = 1:numel(planes)
    subplot(numel(planes),1,p);
    plot(y*1e3, I_acc(p,:)./max(I_acc(p,:)+eps), 'LineWidth', 1.2);
    grid on;
    xlabel('y [mm]'); ylabel('Norm. Intensity');
    title(sprintf('%s (z = %.0f mm)', planes(p).name, planes(p).z*1e3));
    xlim([-4 4]); % view ±4 mm
end

% Optional: visualize the Fourier plane spectrum in angle (ky)
% figure; plot( (ky/(2*pi))*lambda0, fftshift(I_acc(3,:))); xlabel('sin \theta \approx y'''); title('Fourier-plane angular spectrum (norm)');

end
