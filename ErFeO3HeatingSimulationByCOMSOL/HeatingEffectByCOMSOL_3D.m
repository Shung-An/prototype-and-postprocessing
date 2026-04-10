% ErFeO3 heating under a focused 780 nm femtosecond laser using COMSOL LiveLink.
% This script builds a full 3D heat-transfer model for a cylindrical sample.
% It solves a stationary thermal problem and sweeps incident average power.

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

	if isempty(which('mphstart'))
		try
			found = dir('C:\Program Files\COMSOL\**\mli\mphstart.m');
			if ~isempty(found)
				addpath(found(1).folder);
				rehash toolboxcache;
			end
		catch
		end
	end
end

if ~exist('com.comsol.model.util.ModelUtil', 'class')
	if isempty(which('mphstart'))
		error(['COMSOL LiveLink for MATLAB not found in MATLAB path. ' ...
			   'Please add the COMSOL mli folder first.']);
	end

	try
		mphstart(2036);
	catch ME
		error(['Could not connect to COMSOL via mphstart(2036). ' ...
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
model.label('ErFeO3_Heating_780nm_3D.mph');

%% Laser Parameters
model.param.set('lambda0', '780[nm]', 'Laser wavelength');
model.param.set('tauP', '100[fs]', 'Pulse duration');
model.param.set('fRep', '76[MHz]', 'Pulse repetition rate');
model.param.set('Pavg', '10[mW]', 'Incident average power');
model.param.set('spotDiam', '14[um]', 'Laser spot diameter on sample');
model.param.set('w0', 'spotDiam/2', 'Gaussian beam radius');

%% Sample Geometry Parameters
model.param.set('tSample', '50[um]', 'Sample thickness');
model.param.set('rSample', '250[um]', 'Simulated radial extent');
model.param.set('movieGridN', '121', 'Grid size for top-surface movie export');

%% Thermal Boundary Parameters
model.param.set('T0', '293[K]', 'Ambient temperature');
model.param.set('Text', '293[K]', 'External temperature');
model.param.set('hConv', '10[W/(m^2*K)]', 'Convection coefficient');

%% Optical Absorption Parameters
% Estimated from the provided ErFeO3 absorption plot near 0.78 um.
model.param.set('etaAbs', '0.70', 'Effective absorbed fraction after reflection losses');
model.param.set('alphaOpt', '120[1/cm]', 'Estimated optical absorption coefficient at 780 nm');

%% ErFeO3 Material Parameters
model.param.set('kEr', '3[W/(m*K)]', 'Thermal conductivity');
model.param.set('rhoEr', '7500[kg/m^3]', 'Density');
model.param.set('CpEr', '400[J/(kg*K)]', 'Heat capacity');

% 3D volumetric heat source in Cartesian coordinates.
model.param.set('qvol3d', ...
	'2*etaAbs*Pavg*alphaOpt*exp(-2*((x^2+y^2)/w0^2))*exp(-alphaOpt*z)/(pi*w0^2)', ...
	'Absorbed volumetric heat source in 3D');

%% Geometry
model.component.create('comp1', true);
model.component('comp1').geom.create('geom1', 3);
model.component('comp1').geom('geom1').lengthUnit('um');

model.component('comp1').geom('geom1').create('cyl1', 'Cylinder');
model.component('comp1').geom('geom1').feature('cyl1').set('r', 'rSample');
model.component('comp1').geom('geom1').feature('cyl1').set('h', 'tSample');
model.component('comp1').geom('geom1').feature('cyl1').set('pos', {'0' '0' '0'});
model.component('comp1').geom('geom1').run;

%% Material
model.component('comp1').material.create('mat1', 'Common');
model.component('comp1').material('mat1').label('ErFeO3 (user-defined)');
model.component('comp1').material('mat1').propertyGroup('def').set( ...
	'thermalconductivity', {'kEr' '0' '0' '0' 'kEr' '0' '0' '0' 'kEr'});
model.component('comp1').material('mat1').propertyGroup('def').set('density', 'rhoEr');
model.component('comp1').material('mat1').propertyGroup('def').set('heatcapacity', 'CpEr');

%% Physics
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
		   'Tried interfaces: %s\nDetailed COMSOL messages:\n%s'], ...
		   strjoin(htCandidates, ', '), strjoin(cellstr(htErrors), newline));
end

model.component('comp1').physics('ht').feature('init1').set('Tinit', 'T0');

model.component('comp1').physics('ht').create('hs1', 'HeatSource', 3);
model.component('comp1').physics('ht').feature('hs1').selection.all;
model.component('comp1').physics('ht').feature('hs1').set('Q0', 'qvol3d');

% For a single cylinder, COMSOL uses the three exterior boundaries:
% 1 = curved side, 2 = top, 3 = bottom.

model.component('comp1').physics('ht').create('temp1', 'TemperatureBoundary', 2);
model.component('comp1').physics('ht').feature('temp1').selection.set(3);
model.component('comp1').physics('ht').feature('temp1').set('T0', 'T0');

model.component('comp1').physics('ht').create('hf1', 'HeatFluxBoundary', 2);
model.component('comp1').physics('ht').feature('hf1').selection.set(2);
model.component('comp1').physics('ht').feature('hf1').set('q0', 'hConv*(Text-T)');

model.component('comp1').physics('ht').create('hf2', 'HeatFluxBoundary', 2);
model.component('comp1').physics('ht').feature('hf2').selection.set(1);
model.component('comp1').physics('ht').feature('hf2').set('q0', 'hConv*(Text-T)');

%% Mesh
model.component('comp1').mesh.create('mesh1');
model.component('comp1').mesh('mesh1').autoMeshSize(4);
model.component('comp1').mesh('mesh1').run;

%% Study
model.study.create('std1');
model.study('std1').create('stat', 'Stationary');
model.study('std1').create('param', 'Parametric');
model.study('std1').feature('param').set('pname', {'Pavg'});
model.study('std1').feature('param').set('plistarr', {'range(1[mW],1[mW],100[mW])'});
model.study('std1').feature('param').set('punit', {'mW'});

%% Derived values
model.component('comp1').cpl.create('maxop1', 'Maximum', 'geom1');
model.component('comp1').cpl('maxop1').selection.all;

model.component('comp1').cpl.create('aveop1', 'Average', 'geom1');
model.component('comp1').cpl('aveop1').selection.all;

%% Solve
model.study('std1').run;

%% Results
pVals = mphglobal(model, 'Pavg', 'dataset', 'dset1', 'solnum', 'all');
tMax = mphglobal(model, 'maxop1(T)', 'dataset', 'dset1', 'solnum', 'all');
tAvg = mphglobal(model, 'aveop1(T)', 'dataset', 'dset1', 'solnum', 'all');
dT = tMax - mphglobal(model, 'T0');

resultTable = table(pVals(:)*1e3, tMax(:), tAvg(:), dT(:), ...
	'VariableNames', {'P_mW', 'Tmax_K', 'Tavg_K', 'DeltaTmax_K'});
csvPath = fullfile(outputDir, 'ErFeO3_780nm_3D_power_sweep.csv');
writetable(resultTable, csvPath);

%% Export top-surface temperature movie for the 1..100 mW sweep
gridN = 121;
rSample_um = 250;
tSample_um = 50;
xVec = linspace(-rSample_um, rSample_um, gridN);
yVec = linspace(-rSample_um, rSample_um, gridN);
[Xum, Yum] = meshgrid(xVec, yVec);
insideMask = (Xum.^2 + Yum.^2) <= rSample_um^2;

coords = [Xum(:)'; Yum(:)'; tSample_um*ones(1, numel(Xum))];
moviePath = fullfile(outputDir, 'ErFeO3_780nm_3D_topsurface_1to100mW.mp4');
v = VideoWriter(moviePath, 'MPEG-4');
v.FrameRate = 10;
open(v);

figMovie = figure('Color', 'w', 'Visible', 'off');
for iSol = 1:numel(pVals)
	tTop = mphinterp(model, 'T', 'coord', coords, 'solnum', iSol);
	tTop = reshape(tTop, size(Xum));
	tTop(~insideMask) = NaN;

	imagesc(xVec, yVec, tTop);
	set(gca, 'YDir', 'normal');
	axis image;
	xlabel('x (\mum)');
	ylabel('y (\mum)');
	title(sprintf('Top-surface temperature at %.0f mW', pVals(iSol)*1e3));
	cb = colorbar;
	ylabel(cb, 'Temperature (K)');
	caxis([min(tMax) max(tMax)]);
	drawnow;
	writeVideo(v, getframe(figMovie));
	clf(figMovie);
end

close(v);
close(figMovie);

fprintf('Saved 3D sweep data to %s\n', csvPath);
fprintf('Estimated Tmax at 1 mW:   %.3f K\n', resultTable.Tmax_K(1));
fprintf('Estimated Tmax at 10 mW:  %.3f K\n', resultTable.Tmax_K(10));
fprintf('Estimated Tmax at 100 mW: %.3f K\n', resultTable.Tmax_K(end));
fprintf('Saved 3D top-surface movie as %s\n', moviePath);

mphPath = fullfile(outputDir, 'ErFeO3_Heating_780nm_3D.mph');
mphsave(model, mphPath);
fprintf('Saved 3D COMSOL model as %s\n', mphPath);
