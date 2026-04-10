% ErFeO3 heating under a focused 780 nm femtosecond laser using COMSOL LiveLink.
% This script builds a 2D axisymmetric heat-transfer model and sweeps
% incident average power from 1 to 100 mW.

% Try to make LiveLink for MATLAB available automatically.
if isempty(which('mphstart'))
	comsolMliCandidates = {
		'C:\Program Files\COMSOL\COMSOL64\Multiphysics\mli'
		'C:\Program Files\COMSOL\COMSOL63\Multiphysics\mli'
		'C:\Program Files\COMSOL\COMSOL62\Multiphysics\mli'
		'C:\Program Files\COMSOL\COMSOL61\Multiphysics\mli'
	};

	for iCand = 1:numel(comsolMliCandidates)
		cand = comsolMliCandidates{iCand};
		if exist(fullfile(cand, 'mphstart.m'), 'file') == 2
			addpath(cand);
			rehash toolboxcache;
			break;
		end
	end

	% Fallback: recursive search in Program Files COMSOL installs.
	if isempty(which('mphstart'))
		try
			found = dir('C:\Program Files\COMSOL\**\mli\mphstart.m');
			if ~isempty(found)
				addpath(found(1).folder);
				rehash toolboxcache;
			end
		catch
			% Keep silent; final error message below explains next steps.
		end
	end

	% Final fallback for older MATLAB versions: use cmd.exe search.
	if isempty(which('mphstart')) && ispc
		[statusDir, outDir] = system('dir /s /b "C:\Program Files\COMSOL\*\Multiphysics\mli\mphstart.m"');
		if statusDir == 0
			lines = regexp(strtrim(outDir), '\r?\n', 'split');
			if ~isempty(lines) && ~isempty(lines{1})
				addpath(fileparts(lines{1}));
				rehash toolboxcache;
			end
		end
	end
end

% Ensure COMSOL LiveLink classes are available before using ModelUtil.
if ~exist('com.comsol.model.util.ModelUtil', 'class')
	if isempty(which('mphstart'))
		error(['COMSOL LiveLink for MATLAB not found in MATLAB path. ' ...
			   'Please install/enable LiveLink and add COMSOL mli folder to MATLAB path, e.g. ' ...
			   'C:\\Program Files\\COMSOL\\COMSOL64\\Multiphysics\\mli']);
	end

	try
		mphstart(2036); % Connect to local COMSOL server already running on port 2036.
	catch ME
		error(['Could not connect to COMSOL via mphstart(2036). ' ...
			   'Start COMSOL server first (comsolmphserver -port 2036) or adjust port. ' ...
			   'Original error: ' ME.message]);
	end
end

import com.comsol.model.*
import com.comsol.model.util.*

scriptPath = mfilename('fullpath');
if isempty(scriptPath)
	outputDir = pwd;
else
	outputDir = fileparts(scriptPath);
end

ModelUtil.clear;
model = ModelUtil.create('Model');
model.modelPath(outputDir);
model.label('ErFeO3_Heating_780nm_50um.mph');

%% Parameters
model.param.set('lambda0', '780[nm]', 'Laser wavelength');
model.param.set('tauP', '100[fs]', 'Pulse duration');
model.param.set('fRep', '76[MHz]', 'Pulse repetition rate');
model.param.set('fLens', '20[mm]', 'Lens focal length (metadata)');

model.param.set('Pavg', '1[mW]', 'Incident average power (swept)');
model.param.set('spotDiam', '14[um]', 'Laser spot diameter on sample');
model.param.set('w0', 'spotDiam/2', 'Gaussian beam radius');

model.param.set('tSample', '50[um]', 'Sample thickness');
model.param.set('rSample', '250[um]', 'Simulated radial extent');

model.param.set('T0', '293.15[K]', 'Ambient temperature');
model.param.set('Text', '293.15[K]', 'External temperature');
model.param.set('hConv', '10[W/(m^2*K)]', 'Convection coefficient');

% Optical absorption estimated from the provided ErFeO3 spectrum near
% 0.78 um. The plot suggests alpha is on the order of 100 cm^-1, so use
% 120 cm^-1 as a first-pass value until digitized optical data is available.
model.param.set('etaAbs', '0.70', 'Effective absorbed fraction after reflection losses');
model.param.set('alphaOpt', '120[1/cm]', 'Estimated optical absorption coefficient at 780 nm');

% ErFeO3 thermal properties (replace with measured values if available).
model.param.set('kEr', '3[W/(m*K)]', 'Thermal conductivity');
model.param.set('rhoEr', '7500[kg/m^3]', 'Density');
model.param.set('CpEr', '400[J/(kg*K)]', 'Heat capacity');

% Volumetric absorbed power density (axisymmetric coordinates r,z).
model.param.set('qvol', ...
	'2*etaAbs*Pavg*alphaOpt*exp(-2*r^2/w0^2)*exp(-alphaOpt*z)/(pi*w0^2)', ...
	'Absorbed volumetric heat source');

% Pulse diagnostics for interpretation.
model.param.set('Epulse', 'Pavg/fRep', 'Pulse energy');
model.param.set('Ppeak', 'Epulse/tauP', 'Pulse peak power');
model.param.set('Fpeak', '2*Epulse/(pi*w0^2)', 'Peak fluence for Gaussian pulse');

%% Geometry (2D axisymmetric: r in x-direction, z in y-direction)
model.component.create('comp1', true);
model.component('comp1').geom.create('geom1', 2);
model.component('comp1').geom('geom1').axisymmetric(true);
model.component('comp1').geom('geom1').lengthUnit('um');

model.component('comp1').geom('geom1').create('r1', 'Rectangle');
model.component('comp1').geom('geom1').feature('r1').set('size', {'rSample' 'tSample'});
model.component('comp1').geom('geom1').feature('r1').set('pos', {'0' '0'});
model.component('comp1').geom('geom1').run;

%% Material
model.component('comp1').material.create('mat1', 'Common');
model.component('comp1').material('mat1').label('ErFeO3 (user-defined)');
model.component('comp1').material('mat1').propertyGroup('def').set('thermalconductivity', {'kEr' '0' '0' '0' 'kEr' '0' '0' '0' 'kEr'});
model.component('comp1').material('mat1').propertyGroup('def').set('density', 'rhoEr');
model.component('comp1').material('mat1').propertyGroup('def').set('heatcapacity', 'CpEr');

%% Physics: Heat transfer in solids
% COMSOL 6.4 exposes the solids heat-transfer interface under the generic
% HeatTransfer application mode in its physics registry. Older/exported
% scripts sometimes use HeatTransferInSolids instead, so try both and keep
% the error message informative if the connected session lacks the module.
htCreated = false;
htCandidates = {'HeatTransfer', 'HeatTransferInSolids', 'ht'};
htErrors = strings(0, 1);
for iHt = 1:numel(htCandidates)
	try
		model.component('comp1').physics.create('ht', htCandidates{iHt}, 'geom1');
		htCreated = true;
		fprintf('Created COMSOL heat-transfer physics with interface "%s".\n', htCandidates{iHt});
		break;
	catch ME
		htErrors(end+1, 1) = string(sprintf('%s -> %s', htCandidates{iHt}, ME.message)); %#ok<SAGROW>
	end
end

if ~htCreated
	error(['Unable to create COMSOL heat-transfer physics. ' ...
		   'Tried interfaces: %s\nThis usually means the MATLAB session is connected ' ...
		   'to a COMSOL server without the Heat Transfer interface/module enabled.\n' ...
		   'Detailed COMSOL messages:\n%s'], ...
		   strjoin(htCandidates, ', '), strjoin(cellstr(htErrors), newline));
end

% The default solids feature already applies to the whole domain in this
% single-domain model, and COMSOL may lock that built-in selection.
model.component('comp1').physics('ht').feature('init1').set('Tinit', 'T0');

% Domain heat source from optical absorption.
model.component('comp1').physics('ht').create('hs1', 'HeatSource', 2);
model.component('comp1').physics('ht').feature('hs1').selection.all;
model.component('comp1').physics('ht').feature('hs1').set('Q0', 'qvol');

% Boundary IDs for rectangle in this axisymmetric model are typically:
% 1 = symmetry axis (r=0), 2 = top surface, 3 = outer radius, 4 = bottom.
% Bottom is clamped to ambient; top and side lose heat by convection.
model.component('comp1').physics('ht').create('temp1', 'TemperatureBoundary', 1);
model.component('comp1').physics('ht').feature('temp1').selection.set(4);
model.component('comp1').physics('ht').feature('temp1').set('T0', 'T0');

model.component('comp1').physics('ht').create('hf1', 'HeatFluxBoundary', 1);
model.component('comp1').physics('ht').feature('hf1').selection.set([2 3]);
model.component('comp1').physics('ht').feature('hf1').set('q0', 'hConv*(Text-T)');

%% Mesh
model.component('comp1').mesh.create('mesh1');
model.component('comp1').mesh('mesh1').autoMeshSize(3);
model.component('comp1').mesh('mesh1').run;

%% Study: stationary sweep over 1..100 mW
model.study.create('std1');
model.study('std1').create('stat', 'Stationary');
model.study('std1').create('param', 'Parametric');
model.study('std1').feature('param').set('pname', {'Pavg'});
model.study('std1').feature('param').set('plistarr', {'range(1[mW],1[mW],100[mW])'});
model.study('std1').feature('param').set('punit', {'W'});

%% Derived values
model.component('comp1').cpl.create('maxop1', 'Maximum', 'geom1');
model.component('comp1').cpl('maxop1').selection.all;

%% Solve
model.study('std1').run;

%% Gather and export results
pVals = mphglobal(model, 'Pavg', 'dataset', 'dset1', 'solnum', 'all');
tMax = mphglobal(model, 'maxop1(T)', 'dataset', 'dset1', 'solnum', 'all');
dT = tMax - mphglobal(model, 'T0');

resultTable = table(pVals(:)*1e3, tMax(:), dT(:), ...
	'VariableNames', {'P_mW', 'Tmax_K', 'DeltaT_K'});
csvPath = fullfile(outputDir, 'ErFeO3_780nm_50um_power_sweep.csv');
writetable(resultTable, csvPath);

figure('Color', 'w');
plot(resultTable.P_mW, resultTable.DeltaT_K, 'LineWidth', 1.8);
xlabel('Incident average power (mW)');
ylabel('Maximum temperature rise \DeltaT (K)');
title('ErFeO3 heating under 780 nm, 100 fs, 76 MHz excitation');
grid on;

fprintf('Saved sweep data to %s\n', csvPath);
fprintf('Temperature rise at 1 mW:   %.4f K\n', resultTable.DeltaT_K(1));
fprintf('Temperature rise at 100 mW: %.4f K\n', resultTable.DeltaT_K(end));

mphPath = fullfile(outputDir, 'ErFeO3_Heating_780nm_50um.mph');
mphsave(model, mphPath);
fprintf('Saved COMSOL model as %s\n', mphPath);

