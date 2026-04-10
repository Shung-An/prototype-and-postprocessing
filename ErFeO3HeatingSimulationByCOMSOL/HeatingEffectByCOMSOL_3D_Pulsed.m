% ErFeO3 pulsed-laser heating in 3D using COMSOL LiveLink for MATLAB.
% This model is intentionally closer in spirit to the COMSOL blog example:
% it uses a time-dependent study and a pulsed Gaussian Beer-Lambert source.
%
% Reference:
% https://www.comsol.com/blogs/modeling-the-pulsed-laser-heating-of-semitransparent-materials

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
model.label('ErFeO3_Heating_780nm_3D_Pulsed.mph');

%% Laser Parameters
model.param.set('lambda0', '780[nm]', 'Laser wavelength');
model.param.set('Pavg', '10[mW]', 'Average incident laser power');
model.param.set('fRep', '76[MHz]', 'Pulse repetition rate');
model.param.set('tauP', '100[fs]', 'Pulse duration');
model.param.set('spotDiam', '14[um]', 'Laser spot diameter on sample');
model.param.set('w0', 'spotDiam/2', 'Gaussian beam radius');
% Estimated from the provided ErFeO3 absorption plot near 0.78 um.
model.param.set('etaAbs', '0.70', 'Effective absorbed fraction after reflection losses');
model.param.set('alphaOpt', '120[1/cm]', 'Estimated Beer-Lambert absorption coefficient at 780 nm');

%% Pulse / Time Parameters
% True fs-resolved pulse trains are too stiff for direct full-device transient
% simulation, so this model uses a square-wave envelope with the same average
% power. Reduce fPulse if you want to explicitly resolve the heating cycle.
model.param.set('dutyCycle', '0.75', 'Laser on-time fraction');
model.param.set('fPulse', '1[kHz]', 'Resolved pulse-envelope frequency');
model.param.set('tPeriod', '1/fPulse', 'Envelope period');
model.param.set('tOn', 'dutyCycle*tPeriod', 'Envelope on-time');
model.param.set('tEnd', '5*tPeriod', 'Total simulation time');

%% Sample Geometry Parameters
model.param.set('tSample', '50[um]', 'Sample thickness');
model.param.set('rSample', '250[um]', 'Sample radius');

%% Thermal Boundary Parameters
model.param.set('T0', '293[K]', 'Ambient temperature');
model.param.set('Text', '293[K]', 'External temperature');
model.param.set('hConv', '10[W/(m^2*K)]', 'Convection coefficient');
model.param.set('epsRad', '0.8', 'Surface emissivity');

%% ErFeO3 Material Parameters
model.param.set('kEr', '3[W/(m*K)]', 'Thermal conductivity');
model.param.set('rhoEr', '7500[kg/m^3]', 'Density');
model.param.set('CpEr', '400[J/(kg*K)]', 'Heat capacity');

%% Derived Laser Expressions
model.param.set('Epulse', 'Pavg/fRep', 'Energy per laser pulse');
model.param.set('Ppeak', 'Epulse/tauP', 'Peak pulse power');
model.param.set('Iavg0', '2*etaAbs*Pavg/(pi*w0^2)', 'Average absorbed peak intensity');

model.func.create('an1', 'Analytic');
model.func('an1').set('funcname', 'pulseenv');
model.func('an1').set('args', 't');
model.func('an1').set('expr', 'if(mod(t,tPeriod)<tOn,1,0)');
model.func('an1').set('plotargs', {'t' '0' 'tEnd'});

model.param.set('qvol3d', ...
	'2*etaAbs*Pavg*alphaOpt*exp(-2*(x^2+y^2)/w0^2)*exp(-alphaOpt*z)*pulseenv(t)/(pi*w0^2*dutyCycle)', ...
	'Time-dependent Beer-Lambert volumetric source');

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
model.component('comp1').material('mat1').label('ErFeO3');
model.component('comp1').material('mat1').propertyGroup('def').set( ...
	'thermalconductivity', {'kEr' '0' '0' '0' 'kEr' '0' '0' '0' 'kEr'});
model.component('comp1').material('mat1').propertyGroup('def').set('density', 'rhoEr');
model.component('comp1').material('mat1').propertyGroup('def').set('heatcapacity', 'CpEr');

%% Physics: Heat Transfer in Solids
htCreated = false;
htCandidates = {'HeatTransfer', 'HeatTransferInSolids', 'ht'};
for iHt = 1:numel(htCandidates)
	try
		model.component('comp1').physics.create('ht', htCandidates{iHt}, 'geom1');
		htCreated = true;
		fprintf('Created COMSOL heat-transfer physics with interface "%s".\n', htCandidates{iHt});
		break;
	catch
	end
end

if ~htCreated
	error('Unable to create COMSOL heat-transfer physics.');
end

model.component('comp1').physics('ht').feature('init1').set('Tinit', 'T0');

model.component('comp1').physics('ht').create('hs1', 'HeatSource', 3);
model.component('comp1').physics('ht').feature('hs1').selection.all;
model.component('comp1').physics('ht').feature('hs1').set('Q0', 'qvol3d');

% Single cylinder boundary IDs: 1=side, 2=top, 3=bottom.
model.component('comp1').physics('ht').create('temp1', 'TemperatureBoundary', 2);
model.component('comp1').physics('ht').feature('temp1').selection.set(3);
model.component('comp1').physics('ht').feature('temp1').set('T0', 'T0');

model.component('comp1').physics('ht').create('hf1', 'HeatFluxBoundary', 2);
model.component('comp1').physics('ht').feature('hf1').selection.set([1 2]);
model.component('comp1').physics('ht').feature('hf1').set('q0', 'hConv*(Text-T)');

% Add radiative cooling to resemble the COMSOL blog setup more closely.
try
	model.component('comp1').physics('ht').create('rad1', 'SurfaceToAmbientRadiation', 2);
	model.component('comp1').physics('ht').feature('rad1').selection.set([1 2]);
	model.component('comp1').physics('ht').feature('rad1').set('Tamb', 'Text');

	radSet = false;
	radPropCandidates = {'epsilon', 'emissivity', 'eps'};
	for iProp = 1:numel(radPropCandidates)
		try
			model.component('comp1').physics('ht').feature('rad1').set(radPropCandidates{iProp}, 'epsRad');
			fprintf('Configured radiation emissivity with property "%s".\n', radPropCandidates{iProp});
			radSet = true;
			break;
		catch
		end
	end

	if ~radSet
		model.component('comp1').physics('ht').feature.remove('rad1');
		fprintf('Surface-to-ambient radiation feature skipped because emissivity property name was not accepted.\n');
	end
catch ME
	fprintf('Surface-to-ambient radiation feature skipped: %s\n', ME.message);
end

%% Mesh
model.component('comp1').mesh.create('mesh1');
model.component('comp1').mesh('mesh1').autoMeshSize(4);
model.component('comp1').mesh('mesh1').run;

%% Probes / Couplings
model.component('comp1').cpl.create('maxop1', 'Maximum', 'geom1');
model.component('comp1').cpl('maxop1').selection.all;

model.component('comp1').cpl.create('aveop1', 'Average', 'geom1');
model.component('comp1').cpl('aveop1').selection.all;

%% Time-Dependent Study
model.study.create('std1');
model.study('std1').create('time', 'Transient');
model.study('std1').feature('time').set('tlist', 'range(0,tPeriod/100,tEnd)');

%% Solve
model.study('std1').run;

%% Results
time_s = mphglobal(model, 't', 'solnum', 'all');
tmax_K = mphglobal(model, 'maxop1(T)', 'solnum', 'all');
tavg_K = mphglobal(model, 'aveop1(T)', 'solnum', 'all');

time_s = time_s(:);
tmax_K = tmax_K(:);
tavg_K = tavg_K(:);

resultTable = table(time_s, tmax_K, tavg_K, ...
	'VariableNames', {'time_s', 'Tmax_K', 'Tavg_K'});
csvPath = fullfile(outputDir, 'ErFeO3_780nm_3D_pulsed_transient.csv');
writetable(resultTable, csvPath);

fprintf('Saved pulsed 3D transient data to %s\n', csvPath);
fprintf('Initial temperature: %.3f K\n', tmax_K(1));
fprintf('Final peak temperature: %.3f K\n', tmax_K(end));
fprintf('Final average temperature: %.3f K\n', tavg_K(end));

mphPath = fullfile(outputDir, 'ErFeO3_Heating_780nm_3D_Pulsed.mph');
mphsave(model, mphPath);
fprintf('Saved pulsed 3D COMSOL model as %s\n', mphPath);
