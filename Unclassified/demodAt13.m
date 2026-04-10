% Reshape array A into a 4x(N/4) array

for ii=1:17
    A=data(1,1:2e+9/10^((ii-1)/2));
    B=data(2,1:2e+9/10^((ii-1)/2));

    A13 = reshape(A(1:end-mod(length(A),24)), 24, []);
    B13 = reshape(B(1:end-mod(length(A),24)), 24, []);

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

    windowSelection =[-1,-1,-1,-1,1,1,1,1,1,1,-1,-1];

    sumSet = randi([0,100],1,12);
    j=12;
    for i=1:j
        sumSet(i)=sum((A13(i,:)-A13(i+12,:)).*(B13(i,:)-B13(i+12,:)));
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
title(['Log-Log plot of Demodulated noise spectrum (Abs)' ],['Sampling Rate = 1 GHz, A_1-A_{13}']);
xlabel('Sample Number N');
ylabel('Noise Correlation Amplitude (V^2)');