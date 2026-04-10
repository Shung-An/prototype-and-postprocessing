reshapedData = readCM('C:\Users\jr151\source\repos\Quantum Measurement UI\results\20241121_154744\cm.bin');

% Access the first array of 128 elements
firstArray = reshapedData(2496:2497, :);

disp(firstArray)
