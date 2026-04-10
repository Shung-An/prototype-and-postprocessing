% Reshape array A into a 4x(N/4) array
clear length;
A=data(1,:);
B=data(2,:);
A2 =reshape(A(1:end-mod(length(A),2)), 2, []);
B2 =reshape(B(1:end-mod(length(A),2)), 2, []);
A3 = reshape(A(1:end-mod(length(A),4)), 4, []);
B3 = reshape(B(1:end-mod(length(A),4)), 4, []);
A4 = reshape(A(1:end-mod(length(A),6)), 6, []);
B4 = reshape(B(1:end-mod(length(A),6)), 6, []);
A5 = reshape(A(1:end-mod(length(A),8)), 8, []);
B5 = reshape(B(1:end-mod(length(A),8)), 8, []);
A6 = reshape(A(1:end-mod(length(A),10)), 10, []);
B6 = reshape(B(1:end-mod(length(A),10)), 10, []);
A7 = reshape(A(1:end-mod(length(A),12)), 12, []);
B7 = reshape(B(1:end-mod(length(A),12)), 12, []);
A8 = reshape(A(1:end-mod(length(A),14)), 14, []);
B8 = reshape(B(1:end-mod(length(A),14)), 14, []);
A9 = reshape(A(1:end-mod(length(A),16)), 16, []);
B9 = reshape(B(1:end-mod(length(A),16)), 16, []);
A10 = reshape(A(1:end-mod(length(A),18)), 18, []);
B10 = reshape(B(1:end-mod(length(A),18)), 18, []);
A11 = reshape(A(1:end-mod(length(A),20)), 20, []);
B11 = reshape(B(1:end-mod(length(A),20)), 20, []);
A12 = reshape(A(1:end-mod(length(A),22)), 22, []);
B12 = reshape(B(1:end-mod(length(A),22)), 22, []);
A13 = reshape(A(1:end-mod(length(A),24)), 24, []);
B13 = reshape(B(1:end-mod(length(A),24)), 24, []);
A14 = reshape(A(1:end-mod(length(A),26)), 26, []);
B14 = reshape(B(1:end-mod(length(A),26)), 26, []);
A15 = reshape(A(1:end-mod(length(A),28)), 28, []);
B15 = reshape(B(1:end-mod(length(A),28)), 28, []);
A16 = reshape(A(1:end-mod(length(A),30)), 30, []);
B16 = reshape(B(1:end-mod(length(A),30)), 30, []);
A17 = reshape(A(1:end-mod(length(A),32)), 32, []);
B17 = reshape(B(1:end-mod(length(A),32)), 32, []);
A18 = reshape(A(1:end-mod(length(A),34)), 34, []);
B18 = reshape(B(1:end-mod(length(A),34)), 34, []);
A19 = reshape(A(1:end-mod(length(A),36)), 36, []);
B19 = reshape(B(1:end-mod(length(A),36)), 36, []);
A20 = reshape(A(1:end-mod(length(A),38)), 38, []);
B20 = reshape(B(1:end-mod(length(A),38)), 38, []);
A21 = reshape(A(1:end-mod(length(A),40)), 40, []);
B21 = reshape(B(1:end-mod(length(A),40)), 40, []);
A22 = reshape(A(1:end-mod(length(A),42)), 42, []);
B22 = reshape(B(1:end-mod(length(A),42)), 42, []);
A23 = reshape(A(1:end-mod(length(A),44)), 44, []);
B23 = reshape(B(1:end-mod(length(A),44)), 44, []);
A24 = reshape(A(1:end-mod(length(A),46)), 46, []);
B24 = reshape(B(1:end-mod(length(A),46)), 46, []);
A25 = reshape(A(1:end-mod(length(A),48)), 48, []);
B25 = reshape(B(1:end-mod(length(A),48)), 48, []);
A26 = reshape(A(1:end-mod(length(A),50)), 50, []);
B26 = reshape(B(1:end-mod(length(A),50)), 50, []);
A27 = reshape(A(1:end-mod(length(A),52)), 52, []);
B27 = reshape(B(1:end-mod(length(A),52)), 52, []);
A28 = reshape(A(1:end-mod(length(A),54)), 54, []);
B28 = reshape(B(1:end-mod(length(A),54)), 54, []);
A29 = reshape(A(1:end-mod(length(A),56)), 56, []);
B29 = reshape(B(1:end-mod(length(A),56)), 56, []);
A30 = reshape(A(1:end-mod(length(A),58)), 58, []);
B30 = reshape(B(1:end-mod(length(A),58)), 58, []);
A31 = reshape(A(1:end-mod(length(A),60)), 60, []);
B31 = reshape(B(1:end-mod(length(A),60)), 60, []);
A32 = reshape(A(1:end-mod(length(A),62)), 62, []);
B32 = reshape(B(1:end-mod(length(A),62)), 62, []);

A33 = reshape(A(1:end-mod(length(A),64)), 64, []);
B33 = reshape(B(1:end-mod(length(A),64)), 64, []);

A34 = reshape(A(1:end-mod(length(A),66)), 66, []);
B34 = reshape(B(1:end-mod(length(A),66)), 66, []);

A35 = reshape(A(1:end-mod(length(A),68)), 68, []);
B35 = reshape(B(1:end-mod(length(A),68)), 68, []);

A36 = reshape(A(1:end-mod(length(A),70)), 70, []);
B36 = reshape(B(1:end-mod(length(A),70)), 70, []);

A37 = reshape(A(1:end-mod(length(A),72)), 72, []);
B37 = reshape(B(1:end-mod(length(A),72)), 72, []);

A38 = reshape(A(1:end-mod(length(A),74)), 74, []);
B38 = reshape(B(1:end-mod(length(A),74)), 74, []);

A39 = reshape(A(1:end-mod(length(A),76)), 76, []);
B39 = reshape(B(1:end-mod(length(A),76)), 76, []);

A40 = reshape(A(1:end-mod(length(A),78)), 78, []);
B40 = reshape(B(1:end-mod(length(A),78)), 78, []);

A41 = reshape(A(1:end-mod(length(A),80)), 80, []);
B41 = reshape(B(1:end-mod(length(A),80)), 80, []);

A42 = reshape(A(1:end-mod(length(A),82)), 82, []);
B42 = reshape(B(1:end-mod(length(A),82)), 82, []);

A43 = reshape(A(1:end-mod(length(A),84)), 84, []);
B43 = reshape(B(1:end-mod(length(A),84)), 84, []);

A44 = reshape(A(1:end-mod(length(A),86)), 86, []);
B44 = reshape(B(1:end-mod(length(A),86)), 86, []);

A45 = reshape(A(1:end-mod(length(A),88)), 88, []);
B45 = reshape(B(1:end-mod(length(A),88)), 88, []);

A46 = reshape(A(1:end-mod(length(A),90)), 90, []);
B46 = reshape(B(1:end-mod(length(A),90)), 90, []);

A47 = reshape(A(1:end-mod(length(A),92)), 92, []);
B47 = reshape(B(1:end-mod(length(A),92)), 92, []);

A48 = reshape(A(1:end-mod(length(A),94)), 94, []);
B48 = reshape(B(1:end-mod(length(A),94)), 94, []);

A49 = reshape(A(1:end-mod(length(A),96)), 96, []);
B49 = reshape(B(1:end-mod(length(A),96)), 96, []);

A50 = reshape(A(1:end-mod(length(A),98)), 98, []);
B50 = reshape(B(1:end-mod(length(A),98)), 98, []);

A51 = reshape(A(1:end-mod(length(A),100)), 100, []);
B51 = reshape(B(1:end-mod(length(A),100)), 100, []);


A52 = reshape(A(1:end-mod(length(A),102)), 102, []);
B52 = reshape(B(1:end-mod(length(A),102)), 102, []);


A53 = reshape(A(1:end-mod(length(A),104)), 104, []);
B53 = reshape(B(1:end-mod(length(A),104)), 104, []);


A54 = reshape(A(1:end-mod(length(A),106)), 106, []);
B54 = reshape(B(1:end-mod(length(A),106)), 106, []);


A55 = reshape(A(1:end-mod(length(A),108)), 108, []);
B55 = reshape(B(1:end-mod(length(A),108)), 108, []);


A56 = reshape(A(1:end-mod(length(A),110)), 110, []);
B56 = reshape(B(1:end-mod(length(A),110)), 110, []);


A57 = reshape(A(1:end-mod(length(A),112)), 112, []);
B57 = reshape(B(1:end-mod(length(A),112)), 112, []);

A58 = reshape(A(1:end-mod(length(A),114)), 114, []);
B58 = reshape(B(1:end-mod(length(A),114)), 114, []);

A59 = reshape(A(1:end-mod(length(A),116)), 116, []);
B59 = reshape(B(1:end-mod(length(A),116)), 116, []);

A60 = reshape(A(1:end-mod(length(A),118)), 118, []);
B60 = reshape(B(1:end-mod(length(A),118)), 118, []);
A61 = reshape(A(1:end-mod(length(A),120)), 120, []);
B61 = reshape(B(1:end-mod(length(A),120)), 120, []);

A62 = reshape(A(1:end-mod(length(A),122)), 122, []);
B62 = reshape(B(1:end-mod(length(A),122)), 122, []);

A63 = reshape(A(1:end-mod(length(A),124)), 124, []);
B63 = reshape(B(1:end-mod(length(A),124)), 124, []);

A64 = reshape(A(1:end-mod(length(A),126)), 126, []);
B64 = reshape(B(1:end-mod(length(A),126)), 126, []);

A65 = reshape(A(1:end-mod(length(A),128)), 128, []);
B65 = reshape(B(1:end-mod(length(A),128)), 128, []);

A66 = reshape(A(1:end-mod(length(A),130)), 130, []);
B66 = reshape(B(1:end-mod(length(A),130)), 130, []);

A67 = reshape(A(1:end-mod(length(A),132)), 132, []);
B67 = reshape(B(1:end-mod(length(A),132)), 132, []);

A68 = reshape(A(1:end-mod(length(A),134)), 134, []);
B68 = reshape(B(1:end-mod(length(A),134)), 134, []);

A69 = reshape(A(1:end-mod(length(A),136)), 136, []);
B69 = reshape(B(1:end-mod(length(A),136)), 136, []);

A70 = reshape(A(1:end-mod(length(A),138)), 138, []);
B70 = reshape(B(1:end-mod(length(A),138)), 138, []);

A71 = reshape(A(1:end-mod(length(A),140)), 140, []);
B71 = reshape(B(1:end-mod(length(A),140)), 140, []);

A72 = reshape(A(1:end-mod(length(A),142)), 142, []);
B72 = reshape(B(1:end-mod(length(A),142)), 142, []);

A73 = reshape(A(1:end-mod(length(A),144)), 144, []);
B73 = reshape(B(1:end-mod(length(A),144)), 144, []);

A74 = reshape(A(1:end-mod(length(A),146)), 146, []);
B74 = reshape(B(1:end-mod(length(A),146)), 146, []);

A75 = reshape(A(1:end-mod(length(A),148)), 148, []);
B75 = reshape(B(1:end-mod(length(A),148)), 148, []);

A76 = reshape(A(1:end-mod(length(A),150)), 150, []);
B76 = reshape(B(1:end-mod(length(A),150)), 150, []);

A77 = reshape(A(1:end-mod(length(A),152)), 152, []);
B77 = reshape(B(1:end-mod(length(A),152)), 152, []);

A78 = reshape(A(1:end-mod(length(A),154)), 154, []);
B78 = reshape(B(1:end-mod(length(A),154)), 154, []);

A79 = reshape(A(1:end-mod(length(A),156)), 156, []);
B79 = reshape(B(1:end-mod(length(A),156)), 156, []);

A80 = reshape(A(1:end-mod(length(A),158)), 158, []);
B80 = reshape(B(1:end-mod(length(A),158)), 158, []);

A81 = reshape(A(1:end-mod(length(A),160)), 160, []);
B81 = reshape(B(1:end-mod(length(A),160)), 160, []);

A82 = reshape(A(1:end-mod(length(A),162)), 162, []);
B82 = reshape(B(1:end-mod(length(A),162)), 162, []);
A83 = reshape(A(1:end-mod(length(A),164)), 164, []);
B83 = reshape(B(1:end-mod(length(A),164)), 164, []);
A84 = reshape(A(1:end-mod(length(A),166)), 166, []);
B84 = reshape(B(1:end-mod(length(A),166)), 166, []);
A85 = reshape(A(1:end-mod(length(A),168)), 168, []);
B85 = reshape(B(1:end-mod(length(A),168)), 168, []);
A86 = reshape(A(1:end-mod(length(A),170)), 170, []);
B86 = reshape(B(1:end-mod(length(A),170)), 170, []);

A87 = reshape(A(1:end-mod(length(A),172)), 172, []);
B87 = reshape(B(1:end-mod(length(A),172)), 172, []);
A88 = reshape(A(1:end-mod(length(A),174)), 174, []);
B88 = reshape(B(1:end-mod(length(A),174)), 174, []);
A89 = reshape(A(1:end-mod(length(A),176)), 176, []);
B89 = reshape(B(1:end-mod(length(A),176)), 176, []);
A90 = reshape(A(1:end-mod(length(A),178)), 178, []);
B90 = reshape(B(1:end-mod(length(A),178)), 178, []);
A91 = reshape(A(1:end-mod(length(A),180)), 180, []);
B91 = reshape(B(1:end-mod(length(A),180)), 180, []);

A92 = reshape(A(1:end-mod(length(A),182)), 182, []);
B92 = reshape(B(1:end-mod(length(A),182)), 182, []);
A93 = reshape(A(1:end-mod(length(A),184)), 184, []);
B93 = reshape(B(1:end-mod(length(A),184)), 184, []);
A94 = reshape(A(1:end-mod(length(A),186)), 186, []);
B94 = reshape(B(1:end-mod(length(A),186)), 186, []);
A95 = reshape(A(1:end-mod(length(A),188)), 188, []);
B95 = reshape(B(1:end-mod(length(A),188)), 188, []);
A96 = reshape(A(1:end-mod(length(A),190)), 190, []);
B96 = reshape(B(1:end-mod(length(A),190)), 190, []);

A97 = reshape(A(1:end-mod(length(A),192)), 192, []);
B97 = reshape(B(1:end-mod(length(A),192)), 192, []);
A98 = reshape(A(1:end-mod(length(A),194)), 194, []);
B98 = reshape(B(1:end-mod(length(A),194)), 194, []);
A99 = reshape(A(1:end-mod(length(A),196)), 196, []);
B99 = reshape(B(1:end-mod(length(A),196)), 196, []);
A100 = reshape(A(1:end-mod(length(A),198)), 198, []);
B100 = reshape(B(1:end-mod(length(A),198)), 198, []);

for i = 2:100
    Avar{i-1} = eval(['A', num2str(i)]);
end

for i = 2:100
    Bvar{i-1} = eval(['B', num2str(i)]);
end

corf = randi([0, 100], 1, 99);


for j = 1:length (Avar)
    temp = 0;
    for i=1:j
        temp = temp + sum((Avar{j}(i,:)-Avar{j}(i+j,:)).*(Bvar{j}(i,:)-Bvar{j}(i+j,:)));
    end
    corf(j) = temp /(length(A)-mod(length(A),2*j))/2;
end


% figure;
% y=2:1:100;
% plot(y,corf,'r*');
% title(['Demodulated noise spectrum' ],['Sample Rate = 1 GHz']);
% xlabel('Subharmonic demodulation factor (f/n)');
% ylabel('Noise Correlation Amplitude (V^2)');
% 
% grid on;

currentTime = datetime('now', 'Format', 'yyyyMMdd_HHmmss');
filename = 'demodulateData.txt';
fid = fopen(filename, 'a');
fprintf(fid,'%s\t',char(currentTime));
fprintf(fid, '%e\t',corf);
fprintf(fid, '\n');
fclose(fid);

