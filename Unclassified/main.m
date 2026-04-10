switchGPUplot = 0;
switchCorr = 1;
switchShot=0;
switchMotor1=0;
switchMotor2=1;
setPosition1=100;
setPosition2=-100;
frames = 40;

mean_values_elapse = zeros(8,8, frames);
power_values = zeros(4, frames);
sum_mean_values=zeros(1,frames);
stepSize1 = -1;
stepSize2 = 10;

run ('C:/Program Files (x86)/Gage/CompuScope/CompuScope C SDK/Test/iniMotor.m');
disp('Adjusting Motor1...');
command = sprintf('1PR%d', setPosition1);
% Send command to the Picomotor
% Assuming NP_USB is a property of the app containing the USB object
NP_USB.Write(USBADDR, command);
disp('Motot 1 Done!!');
pause(2);
disp('Adjusting Motor2...');
command = sprintf('2PR%d', setPosition2);
% Send command to the Picomotor
% Assuming NP_USB is a property of the app containing the USB object
NP_USB.Write(USBADDR, command);
disp('Motor 2 Done!!');
pause(2);


for ii=1:frames
    fprintf('Cycle %d\n', ii);
    disp('Acq data...');
    run('C:/Program Files (x86)/Gage/CompuScope/CompuScope MATLAB SDK/Main/myAcq.m');
    disp('Acq Done!');
    power_values(:,ii)=NIPowerCheckerCall;
    if switchCorr == 1
        disp('Running Correlation analysis...');
        run ('C:/Program Files (x86)/Gage/CompuScope/CompuScope C SDK/Test/correlationTest.m');
        mean_values_elapse(:,:,ii) = mean_values;
        sum_mean_values(ii)=sum(mean_values,'all');
        disp('Done!!');
    end
    if switchGPUplot == 1
        disp('Running FFT analysis...');
        run ('C:/Program Files (x86)/Gage/CompuScope/CompuScope C SDK/Test/GPUplot.m');
        disp('Done!!');
    end

    if switchShot == 1
        disp('Running Shot noise analysis...');
        run ('C:/Program Files (x86)/Gage/CompuScope/CompuScope C SDK/Test/ShotNoiseTest.m');
        disp('Done!!');
    end

    if switchMotor1 ==1
        disp('Adjusting Motor1...');
        command = sprintf('1PR%d', stepSize1);
        % Send command to the Picomotor
        % Assuming NP_USB is a property of the app containing the USB object
        NP_USB.Write(USBADDR, command);
        disp('Motot 1 Done!!');
    end

    if switchMotor2 ==1
        disp('Adjusting Motor2...');
        command = sprintf('2PR%d', stepSize2);
        % Send command to the Picomotor
        % Assuming NP_USB is a property of the app containing the USB object
        NP_USB.Write(USBADDR, command);
        disp('Motor 2 Done!!');
    end
    pause(0.1);
end
disp('Adjusting Motor1...');
command = sprintf('1PR%d',-setPosition1);
% Send command to the Picomotor
% Assuming NP_USB is a property of the app containing the USB object
NP_USB.Write(USBADDR, command);
disp('Motot 1 Done!!');
pause(1);
disp('Adjusting Motor2...');
command = sprintf('2PR%d',-setPosition2);
% Send command to the Picomotor
% Assuming NP_USB is a property of the app containing the USB object
NP_USB.Write(USBADDR, command);
disp('Motor 2 Done!!');
pause(1);
if switchCorr ==1
    run('C:/Program Files (x86)/Gage/CompuScope/CompuScope C SDK/Test/plotHWPincrement.m');
end