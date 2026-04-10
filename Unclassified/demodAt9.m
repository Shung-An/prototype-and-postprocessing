% Reshape array A into a 4x(N/4) array

for ii=1:13
    A=data(1,1:2e+8/10^((ii-1)/2));
    B=data(2,1:2e+8/10^((ii-1)/2));
clear length
    A9 = reshape(A(1:end-mod(length(A),16)), 16, []);
    B9 = reshape(B(1:end-mod(length(A),16)), 16, []);

    % corf = randi([0, 100], 1, 7);
    % windowSelection = [1,1,1,1,1,1,-1,-1,-1,-1,-1,-1;
    %     -1,1,1,1,1,1,1,-1,-1,-1,-1,-1;
    %     -1,-1,1,1,1,1,1,1,-1,-1,-1,-1;
    %     -1,-1,-1,1,1,1,1,1,1,-1,-1,-1;
    %     -1,-1,-1,-1,1,1,1,1,1,1,-1,-1;
    %     -1,-1,-1,-1,-1,1,1,1,1,1,1,-1;
    %     -1,-1,-1,-1,-1,-1,1,1,1,1,1,1;
    %     1,1,1,1,1,1,1,1,1,1,1,1
    % ];

    windowSelection =[-1,-1,1,1,1,1,-1,-1];

    sumSet = randi([0,100],1,8);
    j=8;
    for i=1:j
        sumSet(i)=sum((A9(i,:)-A9(i+8,:)).*(B9(i,:)-B9(i+8,:)));
    end

    corf(ii)=sum(sumSet.*windowSelection)/(length(A)-mod(length(A),2*j));
    x(ii)=(length(A)-mod(length(A),2*j));
end
% figure;
% y=2:1:100;
% plot(y,corf,'r*');
% title(['Demodulated noise spectrum' ],['Sample Rate = 1 GHz']);
% xlabel('Subharmonic demodulation factor (f/n)');
% ylabel('Noise Correlation Amplitude (V^2)');
%
% grid on;

% currentTime = datetime('now', 'Format', 'yyyyMMdd_HHmmss');
% filename = 'demodulateData.txt';
% fid = fopen(filename, 'a');
% fprintf(fid,'%s\t',char(currentTime));
% fprintf(fid, '%e\t',corf);
% fprintf(fid, '\n');
% fclose(fid);


loglog(x,abs(corf),'r*');
title(['Log-Log plot of Demodulated noise spectrum (Abs)' ],['Sampling Rate = 0.8 GHz (Ext), (A_1-A_{9})\times(B_1-B_{9})']);
xlabel('Sample Number N');
ylabel('Noise Correlation Amplitude (V^2)');