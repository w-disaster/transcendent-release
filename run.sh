python3 ice.py	                  	    \
    --train drebin              	    \
    --test marvin_full          	    \
    -k 10                       	    \
    -n -2                       	    \
    --pval-consider full-train  	    \
    -t random-search            	    \
    -c cred+conf                  	    \
    --rs-max f1_k           	 	    \
    --rs-min f1_r              		    \
    --rs-samples 500
