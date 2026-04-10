function positionLog = recordEsp300Positions(g)
% Records 1024 timestamps of ESP300 positions using GPIB
% Input:
%   g – gpib object (already fopen-ed)
% Output:
%   positionLog – [1024×1] vector of positions (in mm)

    N = 1024;
    positionLog = zeros(N, 1);

    disp("Recording 1024 position timestamps...");

    for i = 1:N
        try
            fprintf(g, "1PA?");
            posStr = fscanf(g);
            pos = str2double(posStr);
            if isnan(pos)
                warning("Non-numeric position at index %d: '%s'", i, posStr);
                pos = NaN;
            end
            positionLog(i) = pos;
        catch ME
            warning("Failed at index %d: %s", i, ME.message);
            positionLog(i) = NaN;
        end
    end

    disp("Done recording 1024 positions.");
end
