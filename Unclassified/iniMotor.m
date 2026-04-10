% Initialize the Picomotor
USBADDR = 1; % Set in the menu of the device, only relevant if multiple are attached
try
    NPasm = NET.addAssembly('C:\Program Files\New Focus\New Focus Picomotor Application\Samples\UsbDllWrap.dll');
    NPASMtype = NPasm.AssemblyHandle.GetType('Newport.USBComm.USB');
    NP_USB = System.Activator.CreateInstance(NPASMtype);
    NP_USB.OpenDevices();

    % Query device information
    querydata = System.Text.StringBuilder(64);
    NP_USB.Query(USBADDR, '*IDN?', querydata);
    devInfo = char(ToString(querydata));
    fprintf(['Device attached is ' devInfo '\n']);
catch ME
    fprintf('Error initializing Picomotor: %s\n', ME.message);
    return;  % Exit the function if initialization fails
end