% Reshape array A into a 4x(N/4) array
for pairs=1:10
    A=data(1,:);
    B=data(2,:);

    xx=24*pairs;
    nn=floor(2000/xx);
    nn=nn/10;
    A =reshape(A(1:end-mod(length(A),xx)), xx, []);
    B =reshape(B(1:end-mod(length(B),xx)), xx, []);
    n=12;
    clear cross;
    %%

    for i=1:n
        switch pairs
            case 1
                cross(i,:)=(A(i,:)-A((n+i),:)).*(B(i,:)-B((n+i),:));
            case 2
                cross(i,:)=(A(i,:)-A((n+i),:)+A(2*n+i,:)-A((3*n+i),:)).*(B(i,:)-B((n+i),:)+B((2*n+i),:)-B((3*n+i),:));
            case 3
                cross(i,:)=(A(i,:)-A((n+i),:)+A(2*n+i,:)-A((3*n+i),:)+A(4*n+i,:)-A((5*n+i),:)).*(B(i,:)-B((n+i),:)+B((2*n+i),:)-B((3*n+i),:)+B((4*n+i),:)-B((5*n+i),:));
            case 4
                cross(i,:)=(A(i,:)-A((n+i),:)+A(2*n+i,:)-A((3*n+i),:)+A(4*n+i,:)-A((5*n+i),:)+A(6*n+i,:)-A((7*n+i),:)).*(B(i,:)-B((n+i),:)+B((2*n+i),:)-B((3*n+i),:)+B((4*n+i),:)-B((5*n+i),:)+B((6*n+i),:)-B((7*n+i),:));
            case 5
                cross(i,:)=(A(i,:)-A((n+i),:)+A(2*n+i,:)-A((3*n+i),:)+A(4*n+i,:)-A((5*n+i),:)+A(6*n+i,:)-A((7*n+i),:)+A(8*n+i,:)-A((9*n+i),:)).*(B(i,:)-B((n+i),:)+B((2*n+i),:)-B((3*n+i),:)+B((4*n+i),:)-B((5*n+i),:)+B((6*n+i),:)-B((7*n+i),:)+B((8*n+i),:)-B((9*n+i),:));
            case 6
                cross(i,:)=(A(i,:)-A((n+i),:)+A(2*n+i,:)-A((3*n+i),:)+A(4*n+i,:)-A((5*n+i),:)+A(6*n+i,:)-A((7*n+i),:)+A(8*n+i,:)-A((9*n+i),:)+A(10*n+i,:)-A((11*n+i),:)).*(B(i,:)-B((n+i),:)+B((2*n+i),:)-B((3*n+i),:)+B((4*n+i),:)-B((5*n+i),:)+B((6*n+i),:)-B((7*n+i),:)+B((8*n+i),:)-B((9*n+i),:)+B((10*n+i),:)-B((11*n+i),:));
            case 7
                cross(i,:)=(A(i,:)-A((n+i),:)+A(2*n+i,:)-A((3*n+i),:)+A(4*n+i,:)-A((5*n+i),:)+A(6*n+i,:)-A((7*n+i),:)+A(8*n+i,:)-A((9*n+i),:)+A(10*n+i,:)-A((11*n+i),:)+A(12*n+i,:)-A((13*n+i),:)).*(B(i,:)-B((n+i),:)+B((2*n+i),:)-B((3*n+i),:)+B((4*n+i),:)-B((5*n+i),:)+B((6*n+i),:)-B((7*n+i),:)+B((8*n+i),:)-B((9*n+i),:)+B((10*n+i),:)-B((11*n+i),:)+B((12*n+i),:)-B((13*n+i),:));
            case 8
                cross(i,:)=(A(i,:)-A((n+i),:)+A(2*n+i,:)-A((3*n+i),:)+A(4*n+i,:)-A((5*n+i),:)+A(6*n+i,:)-A((7*n+i),:)+A(8*n+i,:)-A((9*n+i),:)+A(10*n+i,:)-A((11*n+i),:)+A(12*n+i,:)-A((13*n+i),:)+A(14*n+i,:)-A((15*n+i),:)).*(B(i,:)-B((n+i),:)+B((2*n+i),:)-B((3*n+i),:)+B((4*n+i),:)-B((5*n+i),:)+B((6*n+i),:)-B((7*n+i),:)+B((8*n+i),:)-B((9*n+i),:)+B((10*n+i),:)-B((11*n+i),:)+B((12*n+i),:)-B((13*n+i),:)+B((14*n+i),:)-B((15*n+i),:));
            case 9
                cross(i,:)=(A(i,:)-A((n+i),:)+A(2*n+i,:)-A((3*n+i),:)+A(4*n+i,:)-A((5*n+i),:)+A(6*n+i,:)-A((7*n+i),:)+A(8*n+i,:)-A((9*n+i),:)+A(10*n+i,:)-A((11*n+i),:)+A(12*n+i,:)-A((13*n+i),:)+A(14*n+i,:)-A((15*n+i),:)+A(16*n+i,:)-A((17*n+i),:)).*(B(i,:)-B((n+i),:)+B((2*n+i),:)-B((3*n+i),:)+B((4*n+i),:)-B((5*n+i),:)+B((6*n+i),:)-B((7*n+i),:)+B((8*n+i),:)-B((9*n+i),:)+B((10*n+i),:)-B((11*n+i),:)+B((12*n+i),:)-B((13*n+i),:)+B((14*n+i),:)-B((15*n+i),:)+B((16*n+i),:)-B((17*n+i),:));
            case 10
                cross(i,:)=(A(i,:)-A((n+i),:)+A(2*n+i,:)-A((3*n+i),:)+A(4*n+i,:)-A((5*n+i),:)+A(6*n+i,:)-A((7*n+i),:)+A(8*n+i,:)-A((9*n+i),:)+A(10*n+i,:)-A((11*n+i),:)+A(12*n+i,:)-A((13*n+i),:)+A(14*n+i,:)-A((15*n+i),:)+A(16*n+i,:)-A((17*n+i),:)+A(18*n+i,:)-A((19*n+i),:)).*(B(i,:)-B((n+i),:)+B((2*n+i),:)-B((3*n+i),:)+B((4*n+i),:)-B((5*n+i),:)+B((6*n+i),:)-B((7*n+i),:)+B((8*n+i),:)-B((9*n+i),:)+B((10*n+i),:)-B((11*n+i),:)+B((12*n+i),:)-B((13*n+i),:)+B((14*n+i),:)-B((15*n+i),:)+B((16*n+i),:)-B((17*n+i),:)+B((18*n+i),:)-B((19*n+i),:));
        end
    end
    %%
    wS =[-1,-1,-1,-1,1,1,1,1,1,1,-1,-1];
    if pairs <= 4
        for i=1:8
            if i==1
                noiseEvents(i,2)=wS*cross(:,1);
                noiseEvents(i,1)=i;
            else
                noiseEvents(i,2)=sum(wS*cross(:,1:nn*10^(i-1)))/(nn*10^(i-1));
                noiseEvents(i,1)=nn*10^(i-1);
            end
        end
    else
        for i=1:7
            if i==1
                noiseEvents(i,2)=wS*cross(:,1);
                noiseEvents(i,1)=i;
            else
                noiseEvents(i,2)=sum(wS*cross(:,1:nn*10^(i-1)))/(nn*10^(i-1));
                noiseEvents(i,1)=nn*10^(i-1);
            end
        end
    end
    x(:,pairs)=noiseEvents(:,1);
    y(:,pairs)=noiseEvents(:,2);
    disp(['Pair ' num2str(pairs) ' finished.']);
end
%%
plot(x,y);
loglog(x,abs(y));
xlabel('N');
ylabel('\Delta S');
title('Noise diagnosis');
legend('1', '2', '3', '4', '5', ...
    '6', '7', '8', '9', '10','1/ \sqrt N');
hold on;
% Define the range of x values for the function y = 1/sqrt(x)
x_function = logspace(0, 8, 100);
y_function = 1 ./ sqrt(x_function)./10000000;

% Plot both the dataset and the function on log-log scale
loglog(x_function, y_function, 'LineWidth', 2); % Plot the function
